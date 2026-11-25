"""End-to-end orchestration: RFP text -> structured analysis."""
from __future__ import annotations

from . import analyzer as A
from . import kb as KB
from .diagram import cloud_of
from .llm import enrich


def default_narrative(an: dict) -> dict:
    reqs = an["requirements"]
    n_f = sum(r["type"] == "Functional" for r in reqs)
    mods = [m for m in an["modules"]]
    summary = (f"The client needs a solution covering {len(an['features'])} core capabilities "
               f"({n_f} functional and {len(reqs)-n_f} non-functional requirements identified). "
               f"We recommend Cynbit's {an['stack']['selected']['name']}"
               + (f", reusing {', '.join(mods)} to cut delivery effort." if mods else ".")
               + f" {len(an['ambiguities'])} ambiguous statements and {len(an['missing'])} information gaps should be resolved in discovery.")
    extra = (" A React Native mobile client is added on top of the shared backend." 
             if any(f["id"] == "mobile_app" for f in an["features"]) and an["stack"]["selected"]["id"] != "mobile-first" else "")
    summary += extra
    risks = []
    if an["ambiguities"]:
        risks.append({"risk": "Vague success criteria may cause scope creep", "severity": "High" if len(an["ambiguities"]) > 3 else "Medium",
                      "mitigation": "Convert vague terms into measurable targets in the Discovery phase."})
    if an["out_of_catalog"]:
        risks.append({"risk": "Client mentions technologies outside Cynbit's approved stack: " + ", ".join(o["tech"] for o in an["out_of_catalog"]),
                      "severity": "Medium", "mitigation": "Use an integration adapter or agree an equivalent before signing."})
    if an["facts"]["compliance"] != "None stated":
        risks.append({"risk": f"Regulatory obligations ({an['facts']['compliance']}) affect hosting and audit scope", "severity": "High",
                      "mitigation": "Apply the zero-trust baseline, data-residency controls and audit logging from day one."})
    if any(f["id"] in {"ai_assistant", "document_processing"} for f in an["features"]):
        risks.append({"risk": "LLM answers may be inaccurate or ungrounded", "severity": "Medium",
                      "mitigation": "Retrieval grounding, source citations, refusal on low confidence and human review."})
    if any(m["topic"] == "budget" for m in an["missing"]):
        risks.append({"risk": "No budget stated; proposal may be mis-sized", "severity": "Low", "mitigation": "Offer phased options (MVP vs full scope)."})
    return {"executive_summary": summary, "assumptions": ["Cynbit approved stack is acceptable to the client.",
            "Third-party licence and gateway fees are paid by the client.", "Client provides timely access to stakeholders and data."],
            "additional_questions": [], "risks": risks,
            "architecture_rationale": f"{an['stack']['selected']['name']} best matches the detected capabilities "
                                      f"({', '.join(an['stack_overlap']) or 'general web requirements'})."}


def run_analysis(text: str, llm: dict | None = None) -> dict:
    kb = KB.load_kb()
    features = A.match_features(text)
    stack = A.select_stack(features, text)
    top = stack["ranking"][0]
    an = {"text": text, "requirements": A.extract_requirements(text), "ambiguities": A.detect_ambiguities(text),
          "missing": A.missing_information(text), "facts": A.extract_facts(text), "features": features,
          "out_of_catalog": A.out_of_catalog(text), "stack": stack, "stack_overlap": top["overlap"],
          "similar": A.similar_projects(text), "context": KB.search(text, k=6)}
    an["modules"] = [kb["module_by_feature"][f["id"]]["name"] for f in features if f["id"] in kb["module_by_feature"]]
    an["narrative"], an["llm_used"], an["llm_error"] = default_narrative(an), False, None
    if llm and llm.get("api_key"):
        res, err = enrich(text, an, llm["api_key"], llm["model"], llm.get("provider", "gemini"))
        if res:
            base = an["narrative"]
            an["narrative"] = {k: res.get(k) or base[k] for k in base}
            an["llm_used"] = True
        else:
            an["llm_error"] = err
    return an
