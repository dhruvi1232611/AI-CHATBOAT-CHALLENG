"""Rule-based requirement analysis: extraction, ambiguity detection, feature
matching and guardrails. Deterministic, so it works with no API key."""
import re

from .kb import load_kb

NFR_PATTERNS = {
    "Performance": r"\b(fast|latency|response time|performance|load time|throughput)\b",
    "Scalability": r"\b(scalab\w*|concurrent|\d[\d,]*\s*(users|students|customers|units))\b",
    "Availability": r"\b(uptime|available|availability|sla|disaster|backup)\b",
    "Security & Compliance": r"\b(secur\w*|encrypt\w*|gdpr|hipaa|soc ?2|pci|dpdp|rbi|compliance|comply|audit|privacy|data residency|remain in india)\b",
    "Usability": r"\b(easy to use|user-friendly|intuitive|accessib\w*|seamless)\b",
}
VAGUE = ["fast", "scalable", "easy to use", "user-friendly", "intuitive", "robust", "flexible", "seamless",
         "modern", "as needed", "etc", "best practices", "high performance", "highly available", "good uptime",
         "secure", "some integration", "to be discussed", "tbd", "world-class", "feel"]
PRIORITY = [("Must", r"\b(must|shall|required|mandatory|need to|needs to|need)\b"),
            ("Should", r"\b(should|expected|want|would like)\b"),
            ("Could", r"\b(could|may|nice to have|optional)\b")]
MODAL = re.compile(r"\b(must|shall|should|need\w*|require\w*|will|want|able to|support|provide|enable|allow|include|would like|expect\w*)\b", re.I)
OUT_OF_CATALOG = {r"\bjava\b(?!script)": "Java", r"\.net\b": ".NET", r"\bangular\b": "Angular", r"\bflutter\b": "Flutter",
                  r"\boracle\b": "Oracle", r"\bsap\b": "SAP", r"\bmongodb\b": "MongoDB", r"\blaravel|\bphp\b": "PHP/Laravel",
                  r"\bgcp\b|google cloud": "Google Cloud", r"\bmainframe\b": "Mainframe"}
GENERIC = {"auth", "dashboard_analytics", "admin_panel", "notifications", "search_filter", "file_storage", "integrations"}
MISSING_CHECKS = [
    ("budget", r"\b(budget|inr|rs\.?|usd|\$|lakh|crore)\b", "What is the approved budget range for this engagement?"),
    ("timeline", r"\b(\d+\s*(weeks?|months?)|deadline|go[- ]live|launch date)\b", "What is the target go-live date and are there hard milestones?"),
    ("volume", r"\b\d[\d,]*\s*(users|students|customers|units|employees|tenants|requests)\b", "What are the expected user counts and peak concurrency?"),
    ("cloud", r"\b(aws|azure|cloud|on-prem\w*|data centre|data center)\b", "Do you have a cloud preference or hosting constraints?"),
    ("compliance", r"\b(gdpr|hipaa|soc ?2|pci|dpdp|rbi|compliance|regulat\w*|iso 27001)\b", "Are there regulatory or compliance requirements (data residency, audits)?"),
    ("success", r"\b(kpi|success metric|goal|objective|outcome)\b", "What measurable outcomes define success for this project?"),
]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [re.sub(r"^[\s\-\u2022*\d.)]+", "", p).strip() for p in parts if len(p.split()) >= 5]


def extract_requirements(text: str) -> list[dict]:
    reqs = []
    for s in _sentences(text):
        if not MODAL.search(s) and not re.match(r"^(we|our|the)\b", s, re.I):
            continue
        if re.match(r"^(request for proposal|client:)", s, re.I):
            continue
        nfr = next((c for c, pat in NFR_PATTERNS.items() if re.search(pat, s, re.I)), None)
        prio = next((p for p, pat in PRIORITY if re.search(pat, s, re.I)), "Should")
        reqs.append({"id": f"R{len(reqs)+1:02d}", "text": s, "type": "Non-functional" if nfr else "Functional",
                     "category": nfr or "Capability", "priority": prio})
    return reqs


def detect_ambiguities(text: str) -> list[dict]:
    out = []
    for s in _sentences(text):
        hits = [v for v in VAGUE if re.search(rf"\b{re.escape(v)}\b", s, re.I)]
        if hits:
            out.append({"text": s, "terms": hits, "why": "Unmeasurable wording; needs a testable target (e.g. numbers, SLAs)."})
    return out


def missing_information(text: str) -> list[dict]:
    return [{"topic": t, "question": q} for t, pat, q in MISSING_CHECKS if not re.search(pat, text, re.I)]


def extract_facts(text: str) -> dict:
    facts = {}
    if m := re.search(r"(\d+)\s*(weeks?|months?)", text, re.I):
        facts["timeline"] = f"{m.group(1)} {m.group(2)}"
    if m := re.search(r"\b((?:inr|rs\.?|usd)\s*\d[\d.,\-\s]*(?:lakh|crore|k|m)?|\$\s*\d[\d.,]*(?:k|m)?)", text, re.I):
        facts["budget"] = m.group(1).strip()
    if m := re.search(r"(\d[\d,]*)\s*(users|students|customers|units|employees)", text, re.I):
        facts["scale"] = f"{m.group(1)} {m.group(2)}"
    facts["cloud"] = "Azure" if re.search(r"\bazure\b", text, re.I) else "AWS" if re.search(r"\baws\b", text, re.I) else "Not stated (default AWS)"
    comp = sorted({c.upper() for c in re.findall(r"\b(gdpr|hipaa|dpdp|rbi|pci|soc ?2)\b", text, re.I)})
    facts["compliance"] = ", ".join(comp) or "None stated"
    return facts


def match_features(text: str) -> list[dict]:
    kb, found = load_kb(), []
    for f in kb["features"].values():
        hits = [k for k in f["keywords"] if re.search(rf"(?<!\w){re.escape(k)}", text, re.I)]
        if hits:
            found.append({"id": f["id"], "name": f["name"], "evidence": hits, "score": len(hits)})
    return sorted(found, key=lambda x: -x["score"])


def out_of_catalog(text: str) -> list[dict]:
    return [{"tech": label, "note": "Not in Cynbit's approved stack: confirm, or propose an equivalent."}
            for pat, label in OUT_OF_CATALOG.items() if re.search(pat, text, re.I)]


def select_stack(features: list[dict], text: str) -> dict:
    kb = load_kb()
    ids = {f["id"] for f in features}
    bm = {kb["docs"][i]["id"]: s for i, s in kb["retriever"].search(text, k=len(kb["docs"])) if kb["docs"][i]["type"] == "Stack"}
    scored = []
    for s in kb["cap"]["stacks"]:
        hit = ids & set(s["tags"])
        weight = sum(0.5 if h in GENERIC else 3 for h in hit)  # specialised capabilities decide the stack
        scored.append({"stack": s, "score": round(weight + bm.get(s["id"], 0), 2), "overlap": sorted(hit)})
    scored.sort(key=lambda x: -x["score"])
    return {"selected": scored[0]["stack"], "ranking": scored}


def similar_projects(text: str, k: int = 3) -> list[dict]:
    kb = load_kb()
    ranked = kb["retriever"].search(text, k=len(kb["docs"]))
    out = []
    for i, s in ranked:
        d = kb["docs"][i]
        if d["type"] == "Past project":
            p = next(x for x in kb["projects"] if x["id"] == d["id"])
            out.append({**p, "similarity": s, "ratio": p["actual_hours"] / p["estimated_hours"]})
        if len(out) == k:
            break
    return out
