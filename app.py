"""Cynbit RFP-to-Architecture & Scoping Copilot: Streamlit proof of concept."""
from __future__ import annotations
import json
import os

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src import kb as KB
from src.config import COMPLEXITY, LLM_PROVIDERS
from src.diagram import architecture, cloud_of, deployment
from src.estimator import estimate
from src.ingestion import list_samples, read_upload
from src.pipeline import run_analysis
from src.report import to_markdown

st.set_page_config(page_title="Cynbit Scoping Copilot", page_icon="🧭", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700&family=Instrument+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Instrument Sans', sans-serif; }
h1, h2, h3 { font-family: 'Bricolage Grotesque', sans-serif; letter-spacing: -0.01em; }
.hero { background:#12332E; color:#EAF3EF; padding:28px 32px; border-radius:6px; margin-bottom:18px; }
.hero h1 { color:#fff; margin:0 0 6px 0; font-size:2rem; }
.hero p { margin:0; color:#B8D3CB; max-width:62ch; line-height:1.5; }
.pill { display:inline-block; padding:3px 10px; border-radius:99px; font-size:.78rem; font-weight:600; margin-right:6px; }
.pill.on { background:#CDEBE3; color:#0B4F46; } .pill.off { background:#F3E2C7; color:#7A4A0E; }
.card { border:1px solid #D5DDD9; background:#fff; border-radius:6px; padding:14px 16px; margin-bottom:10px; }
.card b { color:#12332E; } .muted { color:#5A6B66; font-size:.88rem; }
.sev-High { color:#B42318; font-weight:600; } .sev-Medium { color:#B45309; font-weight:600; } .sev-Low { color:#0F766E; font-weight:600; }
div[data-testid="stMetric"] { background:#fff; border:1px solid #D5DDD9; border-radius:6px; padding:12px 14px; }
</style>
""", unsafe_allow_html=True)


def mermaid(code: str, height: int = 460):
    components.html(f"""<div class="mermaid" style="font-family:sans-serif">{code}</div>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
    <script>mermaid.initialize({{startOnLoad:true,theme:"neutral",flowchart:{{curve:"basis"}}}});</script>""",
                    height=height, scrolling=True)


def secret_key(name: str) -> str:
    try:
        return st.secrets.get(name, "")
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("1. Provide the RFP")
    source = st.radio("Source", ["Sample RFP", "Paste text", "Upload file"], label_visibility="collapsed")
    rfp_text = ""
    if source == "Sample RFP":
        samples = list_samples()
        pick = st.selectbox("Choose a sample", list(samples))
        rfp_text = st.text_area("RFP text (editable)", samples[pick], height=220, key=f"sample_{pick}")
    elif source == "Paste text":
        rfp_text = st.text_area("Paste RFP, brief or call transcript", height=260)
    else:
        up = st.file_uploader("PDF, DOCX or TXT", type=["pdf", "docx", "txt"])
        if up:
            rfp_text = read_upload(up.name, up.getvalue())
            st.caption(f"Read {len(rfp_text.split())} words from {up.name}")

    st.header("2. Team & rates")
    team = st.slider("Developers on the team", 2, 12, 4)
    hpw = st.slider("Productive hours per developer per week", 20, 40, 30)
    sprint_weeks = st.select_slider("Sprint length (weeks)", [1, 2, 3, 4], value=2)
    rate = st.number_input("Blended rate (INR / hour)", 300, 10000, 1200, 100)

    st.header("3. Estimation controls")
    risk_factor = st.slider("Risk appetite (buffer multiplier)", 0.5, 1.5, 1.0, 0.1)
    use_modules = st.toggle("Apply Cynbit module reuse", True)
    use_calib = st.toggle("Calibrate with past project velocity", True)

    st.header("4. Optional LLM layer")
    use_llm = st.toggle("Enhance narrative with an LLM", False)
    api_key = model = provider = ""
    if use_llm:
        label = st.selectbox("Provider", list(LLM_PROVIDERS))
        provider, default_model = LLM_PROVIDERS[label]
        env = "GEMINI_API_KEY" if provider == "gemini" else "ANTHROPIC_API_KEY"
        api_key = st.text_input("API key", value=os.getenv(env, secret_key(env)), type="password",
                                help="Free Gemini key: aistudio.google.com" if provider == "gemini" else "console.anthropic.com")
        model = st.text_input("Model", default_model)

    run = st.button("Analyze RFP", type="primary", use_container_width=True, disabled=not rfp_text.strip())

settings = {"team_size": team, "hours_per_dev_week": hpw, "sprint_weeks": sprint_weeks, "rate": rate,
            "risk_factor": risk_factor, "use_modules": use_modules, "use_calibration": use_calib}

# ---------------------------------------------------------------- hero
st.markdown("""<div class="hero"><h1>RFP-to-Architecture Scoping Copilot</h1>
<p>Turn an unstructured RFP into requirements, discovery questions, an architecture grounded in Cynbit's own stacks,
and a phased estimate. A senior architect reviews before anything reaches the client.</p></div>""", unsafe_allow_html=True)

if run:
    with st.spinner("Analyzing RFP against the Cynbit knowledge base..."):
        st.session_state.analysis = run_analysis(rfp_text, {"api_key": api_key, "model": model, "provider": provider} if use_llm and api_key else None)
        st.session_state.run_id = st.session_state.get("run_id", 0) + 1

an = st.session_state.get("analysis")
if not an:
    st.info("Pick a sample RFP in the sidebar and select **Analyze RFP**. Every number on this page updates live as you change inputs.")
    st.stop()

kb = KB.load_kb()
mode = "on" if an["llm_used"] else "off"
st.markdown(f'<span class="pill {mode}">{"LLM-enhanced narrative" if an["llm_used"] else "Rule-based engine"}</span>'
            f'<span class="pill on">{len(an["requirements"])} requirements</span><span class="pill on">{len(an["features"])} capabilities</span>',
            unsafe_allow_html=True)
if an["llm_error"]:
    st.warning(f"LLM call failed, showing the rule-based result instead. {an['llm_error']}")

t_over, t_req, t_arch, t_est, t_kb, t_exp = st.tabs(["Overview", "Requirements", "Architecture", "Estimate", "Knowledge base", "Export"])

# ---------------------------------------------------------------- estimate (runs first so every tab can use it)
with t_est:
    st.subheader("Scope & estimate")
    st.caption("Change inclusion or complexity and the whole estimate recalculates.")
    detected = {f["id"]: f for f in an["features"]}
    extras = st.multiselect("Add capabilities from the Cynbit catalog", [i for i in kb["features"] if i not in detected],
                            format_func=lambda i: kb["features"][i]["name"])
    rows = [{"id": f["id"], "Include": True, "Feature": f["name"], "Complexity": "L" if f["score"] >= 3 else "M",
             "Evidence": ", ".join(f["evidence"][:3])} for f in an["features"]]
    rows += [{"id": i, "Include": True, "Feature": kb["features"][i]["name"], "Complexity": "M", "Evidence": "added manually"} for i in extras]
    edited = st.data_editor(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                            key=f"feat_{st.session_state.run_id}_{'-'.join(sorted(extras))}",
                            column_config={"id": None, "Include": st.column_config.CheckboxColumn(width="small"),
                                           "Complexity": st.column_config.SelectboxColumn(options=list(COMPLEXITY), width="small", help="S=0.6x, M=1x, L=1.6x"),
                                           "Feature": st.column_config.TextColumn(disabled=True), "Evidence": st.column_config.TextColumn(disabled=True)})
    selection = [{"id": r["id"], "complexity": r["Complexity"]} for _, r in edited.iterrows() if r["Include"]]
    est = estimate(selection, an, settings)

    c = st.columns(4)
    c[0].metric("Total effort", f"{est['total_hours']:,} h", f"range {est['low']:,}-{est['high']:,}", delta_color="off")
    c[1].metric("Duration", f"~{est['weeks']} weeks", f"{est['sprints']} sprints", delta_color="off")
    c[2].metric("Indicative cost", f"INR {est['cost']/100000:.1f} L")
    c[3].metric("Confidence", est["confidence"], f"{int(est['buffer']*100)}% risk buffer", delta_color="off")
    st.markdown(f'<p class="muted">Formula: {est["base_hours"]} base hrs (after {est["reuse_saved"]} hrs module reuse) x {est["multiplier"]} NFR multiplier '
                f'x {est["calibration"]} velocity calibration x {1+est["buffer"]:.2f} risk buffer.</p>', unsafe_allow_html=True)
    a, b = st.columns(2)
    with a:
        st.markdown("**Hours by phase** (Cynbit's six-stage lifecycle)")
        st.bar_chart(pd.DataFrame(est["phases"]).set_index("Phase")["Hours"], color="#0F766E")
    with b:
        st.markdown("**Hours by role**")
        st.bar_chart(pd.Series(est["roles"], name="Hours"), color="#B45309")
    st.markdown("**Work breakdown**")
    st.dataframe(pd.DataFrame(est["rows"]).drop(columns="id"), hide_index=True, use_container_width=True)

ids = {s["id"] for s in selection}
active_modules = [kb["module_by_feature"][i]["name"] for i in ids if i in kb["module_by_feature"]] if use_modules else []
cloud = cloud_of(an)
arch_code = architecture(an["stack"]["selected"], ids, active_modules)

# ---------------------------------------------------------------- overview
with t_over:
    n = an["narrative"]
    st.subheader("Executive summary")
    st.write(n["executive_summary"])
    f = an["facts"]
    cols = st.columns(5)
    for col, (k, label) in zip(cols, [("scale", "Scale"), ("timeline", "Timeline"), ("budget", "Budget"), ("cloud", "Cloud"), ("compliance", "Compliance")]):
        col.metric(label, f.get(k, "Not stated"))
    l, r = st.columns(2)
    with l:
        st.subheader("Risks")
        for x in n["risks"] or [{"risk": "No major risks detected from the text alone.", "severity": "Low", "mitigation": "Confirm in discovery."}]:
            st.markdown(f'<div class="card"><span class="sev-{x["severity"]}">{x["severity"]}</span> &nbsp;<b>{x["risk"]}</b>'
                        f'<div class="muted">{x["mitigation"]}</div></div>', unsafe_allow_html=True)
    with r:
        st.subheader("Assumptions")
        for a_ in n["assumptions"]:
            st.markdown(f"- {a_}")
        if an["out_of_catalog"]:
            st.subheader("Guardrail flags")
            for o in an["out_of_catalog"]:
                st.warning(f"**{o['tech']}**: {o['note']}")

# ---------------------------------------------------------------- requirements
with t_req:
    st.subheader("Extracted requirements")
    kinds = st.multiselect("Show", ["Functional", "Non-functional"], default=["Functional", "Non-functional"])
    rdf = pd.DataFrame(an["requirements"])
    st.dataframe(rdf[rdf["type"].isin(kinds)].rename(columns={"id": "ID", "text": "Requirement", "type": "Type", "category": "Category", "priority": "Priority"}),
                 hide_index=True, use_container_width=True)
    l, r = st.columns(2)
    with l:
        st.subheader(f"Ambiguities ({len(an['ambiguities'])})")
        for x in an["ambiguities"] or []:
            st.markdown(f'<div class="card">{x["text"]}<div class="muted">Vague: {", ".join(x["terms"])}. {x["why"]}</div></div>', unsafe_allow_html=True)
        if not an["ambiguities"]:
            st.success("No vague wording detected.")
    with r:
        st.subheader("Questions to ask the client")
        qs = [m["question"] for m in an["missing"]] + an["narrative"]["additional_questions"]
        for q in qs:
            st.checkbox(q, key=f"q_{hash(q)}")
        if not qs:
            st.success("The RFP covers all standard discovery topics.")

# ---------------------------------------------------------------- architecture
with t_arch:
    s = an["stack"]["selected"]
    st.subheader(f"Recommended: {s['name']}")
    st.write(an["narrative"]["architecture_rationale"])
    st.dataframe(pd.DataFrame([{"Layer": k.title(), "Technology": v} for k, v in s["components"].items()]), hide_index=True, use_container_width=True)
    st.markdown("**Component architecture** (updates with your scope selection)")
    mermaid(arch_code, 480)
    st.markdown(f"**Deployment topology on {cloud}**")
    mermaid(deployment(cloud, ids), 420)
    with st.expander("Stack ranking"):
        st.dataframe(pd.DataFrame([{"Stack": r_["stack"]["name"], "Score": r_["score"], "Matched capabilities": ", ".join(r_["overlap"])} for r_ in an["stack"]["ranking"]]),
                     hide_index=True, use_container_width=True)
    with st.expander("Security baselines applied to every Cynbit deployment"):
        for b in kb["cap"]["baselines"]:
            st.markdown(f"- **{b['name']}**: {b['description']}")
    st.subheader("Most similar past projects")
    st.dataframe(pd.DataFrame([{"Project": p["name"], "Domain": p["domain"], "Similarity": p["similarity"], "Estimated h": p["estimated_hours"],
                                "Actual h": p["actual_hours"], "Overrun": f"{(p['ratio']-1)*100:.0f}%"} for p in an["similar"]]),
                 hide_index=True, use_container_width=True)
    st.caption("Historical overruns feed the velocity calibration factor in the estimate.")

# ---------------------------------------------------------------- knowledge base
with t_kb:
    st.subheader("Search the Cynbit capabilities knowledge base")
    q = st.text_input("Try: 'document OCR for scanned files', 'property management', 'zero trust'", "")
    kind = st.selectbox("Type", ["All", "Stack", "Module", "Baseline", "Past project"])
    if q:
        for h in KB.search(q, k=6, doc_type=None if kind == "All" else kind):
            st.markdown(f'<div class="card"><b>{h["title"]}</b> <span class="muted">{h["type"]} · relevance {h["score"]}</span>'
                        f'<div class="muted">{h["text"]}</div></div>', unsafe_allow_html=True)
    else:
        st.markdown("**Reusable modules**")
        st.dataframe(pd.DataFrame(kb["cap"]["modules"]).drop(columns="id"), hide_index=True, use_container_width=True)
        st.markdown("**Approved stacks**")
        st.dataframe(pd.DataFrame([{"Stack": x["name"], "Best for": x["best_for"], "Components": ", ".join(x["components"].values())} for x in kb["cap"]["stacks"]]),
                     hide_index=True, use_container_width=True)
    st.caption("Retrieval is hybrid BM25 plus fuzzy n-gram matching. Production would use embeddings in Qdrant.")

# ---------------------------------------------------------------- export
with t_exp:
    md = to_markdown(an, est, arch_code, settings)
    st.subheader("Proposal draft")
    d = st.columns(3)
    d[0].download_button("Download proposal (.md)", md, "proposal_draft.md", "text/markdown", use_container_width=True)
    d[1].download_button("Download estimate (.csv)", pd.DataFrame(est["rows"]).drop(columns="id").to_csv(index=False), "estimate.csv", "text/csv", use_container_width=True)
    d[2].download_button("Download analysis (.json)", json.dumps({k: v for k, v in an.items() if k not in ("context", "text")}, indent=2, default=str),
                         "analysis.json", "application/json", use_container_width=True)
    st.markdown(md)
