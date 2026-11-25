"""Optional LLM enrichment (Google Gemini by default, Anthropic also supported).
Grounded in retrieved KB context; the deterministic engine still owns features,
stack and estimate, so the LLM can't invent scope. Never raises."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
import re
import urllib.error
import urllib.request

SYSTEM = """You are a senior solution architect at Cynbit Technologies assisting with RFP scoping.
Use ONLY technologies listed in the provided Cynbit context. Never invent facts about the client.
If information is missing, say so. Respond with a single JSON object and nothing else."""

PROMPT = """RFP:
\"\"\"{rfp}\"\"\"

Cynbit context (approved stacks, modules, baselines, similar past projects):
{context}

Rule-based findings: {findings}

Return JSON with keys:
"executive_summary": 3-4 sentence summary for the client-facing proposal,
"assumptions": list of up to 5 assumptions,
"additional_questions": list of up to 4 sharp discovery questions not already covered,
"risks": list of up to 5 objects {{"risk":..., "severity":"High|Medium|Low", "mitigation":...}},
"architecture_rationale": 3-4 sentences explaining why the chosen stack fits, using only context technologies."""

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_FALLBACKS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]  # tried if the chosen model is unavailable/rate-limited
RETRY_CODES = {404, 429, 500, 503}


def _parse(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


def _build_prompt(rfp: str, analysis: dict) -> str:
    ctx = "\n".join(f'- [{d["type"]}] {d["text"]}' for d in analysis["context"])
    findings = json.dumps({"stack": analysis["stack"]["selected"]["name"], "features": [f["name"] for f in analysis["features"]],
                           "ambiguities": len(analysis["ambiguities"]), "facts": analysis["facts"]})
    return PROMPT.format(rfp=rfp[:6000], context=ctx, findings=findings)


def _call_gemini(prompt: str, api_key: str, model: str) -> str:
    models = [model] + [m for m in GEMINI_FALLBACKS if m != model]
    last = "no model tried"
    for m in models:
        body = json.dumps({"systemInstruction": {"parts": [{"text": SYSTEM}]},
                           "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                           "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}).encode()
        req = urllib.request.Request(GEMINI_URL.format(model=m), data=body, method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": api_key})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        except urllib.error.HTTPError as e:
            last = f"{m}: HTTP {e.code}"
            if e.code not in RETRY_CODES:   # e.g. 400/403 = bad key; no point trying other models
                raise RuntimeError(f"{last}. Check your API key.") from e
        except (KeyError, IndexError) as e:
            last = f"{m}: unexpected response ({e})"
    raise RuntimeError(f"All Gemini models failed. Last: {last}. Free-tier quota may be used up; try again later.")


def _call_anthropic(prompt: str, api_key: str, model: str) -> str:
    import anthropic
    msg = anthropic.Anthropic(api_key=api_key).messages.create(
        model=model, max_tokens=1800, system=SYSTEM, messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if b.type == "text")


def enrich(rfp: str, analysis: dict, api_key: str, model: str, provider: str = "gemini") -> tuple[dict | None, str | None]:
    """Returns (result, error). Never raises, so the app falls back gracefully."""
    try:
        prompt = _build_prompt(rfp, analysis)
        text = (_call_gemini if provider == "gemini" else _call_anthropic)(prompt, api_key, model)
        return _parse(text), None
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"