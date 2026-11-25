
"""Cynbit capabilities knowledge base loader and search."""
from __future__ import annotations


import json
from functools import lru_cache

from .config import KB_DIR
from .retriever import HybridRetriever


def _load(name):
    return json.loads((KB_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_kb() -> dict:
    cap, projects, features = _load("capabilities.json"), _load("projects.json"), _load("features.json")
    docs = []
    for s in cap["stacks"]:
        comp = ", ".join(f"{k}: {v}" for k, v in s["components"].items())
        docs.append({"type": "Stack", "id": s["id"], "title": s["name"],
                     "text": f'{s["name"]}. {s["description"]} Best for {s["best_for"]}. {comp}'})
    for m in cap["modules"]:
        docs.append({"type": "Module", "id": m["id"], "title": m["name"], "text": f'{m["name"]}. {m["description"]}'})
    for b in cap["baselines"]:
        docs.append({"type": "Baseline", "id": b["id"], "title": b["name"], "text": f'{b["name"]}. {b["description"]}'})
    for p in projects:
        docs.append({"type": "Past project", "id": p["id"], "title": p["name"], "text": f'{p["name"]} ({p["domain"]}). {p["summary"]}'})
    return {"cap": cap, "projects": projects, "features": {f["id"]: f for f in features},
            "docs": docs, "retriever": HybridRetriever([d["text"] for d in docs]),
            "modules": {m["id"]: m for m in cap["modules"]},
            "module_by_feature": {m["feature"]: m for m in cap["modules"]}}


def search(query: str, k: int = 5, doc_type: str | None = None) -> list[dict]:
    kb = load_kb()
    hits = kb["retriever"].search(query, k=len(kb["docs"]))
    out = []
    for i, s in hits:
        d = kb["docs"][i]
        if doc_type and d["type"] != doc_type:
            continue
        out.append({**d, "score": s})
        if len(out) == k:
            break
    return out
