# Cynbit RFP-to-Architecture & Scoping Copilot (Proof of Concept)

An interactive Streamlit app that turns an unstructured RFP into requirements, discovery questions,
a Cynbit-grounded architecture and a phased estimate, in minutes instead of days. A senior architect
reviews the output before anything reaches a client.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
It works with **no API key** (deterministic rule-based engine). To add an LLM-written summary, risks and
extra questions, switch on **Enhance narrative with an LLM** in the sidebar and paste an Anthropic API key
(or set `ANTHROPIC_API_KEY`). If the call fails, the app falls back automatically.

## What is dynamic
- Paste, upload (PDF/DOCX/TXT) or edit any RFP; everything is recomputed from the text.
- Feature inclusion and complexity (S/M/L) are editable; add catalog capabilities manually.
- Team size, rates, sprint length, risk appetite, module reuse and velocity calibration all update the estimate live.
- Architecture and deployment diagrams (Mermaid) are generated from the selected scope and the cloud mentioned in the RFP.
- Knowledge-base search is live; exports (Markdown proposal, CSV, JSON) reflect your current choices.

## Pipeline
1. **Ingestion** (`src/ingestion.py`): PDF, DOCX, TXT.
2. **Analysis** (`src/analyzer.py`): requirement extraction, NFR classification, ambiguity detection, missing-info questions, fact extraction.
3. **Grounding** (`src/kb.py`, `src/retriever.py`): hybrid BM25 + n-gram retrieval over stacks, modules, baselines and past projects.
4. **Guardrails**: stacks come only from the knowledge base; technologies outside it (Java, .NET, ...) are flagged.
5. **Estimation** (`src/estimator.py`): feature hours x complexity, minus module reuse, x NFR multiplier, x historical velocity, plus risk buffer, split over Cynbit's six phases and roles.
6. **LLM layer** (`src/llm.py`, optional): grounded JSON enrichment; it can't change features, stack or hours.
7. **Export** (`src/report.py`).

## Structure
```
app.py                    Streamlit UI
src/                      config, ingestion, retriever, kb, analyzer, estimator, diagram, llm, pipeline, report
data/knowledge_base/      capabilities.json, features.json, projects.json
data/sample_rfps/         three sample RFPs
tests/                    pipeline and app smoke tests  (run: pytest)
```

## Important notes
- The knowledge base is **illustrative**, based on public Cynbit information. Replace the JSON files with real internal data.
- Past-project hours are synthetic placeholders; calibration only becomes meaningful with real data.
- The retriever is lightweight by design. Production would use embeddings and Qdrant.

## Roadmap
Embedding retrieval in Qdrant, evaluation set of past RFPs, CRM integration, architect feedback loop, PDF/Word proposal export.
