"""Effort estimation: feature hours x complexity, minus module reuse,
calibrated against historical velocity and padded with a risk buffer."""
import math

from .config import COMPLEXITY, FIXED_FEATURES, PHASES, PM_SHARE, ROLE_MIX
from .kb import load_kb


def risk_buffer(analysis: dict, factor: float = 1.0) -> float:
    pct = 0.10 + 0.02 * len(analysis["ambiguities"]) + 0.015 * len(analysis["missing"]) + 0.03 * len(analysis["out_of_catalog"])
    return round(min(pct * factor, 0.45), 3)


def calibration(analysis: dict) -> float:
    sim = analysis["similar"]
    if not sim:
        return 1.0
    w = sum(s["similarity"] for s in sim) or 1
    return round(min(max(sum(s["ratio"] * s["similarity"] for s in sim) / w, 0.9), 1.4), 3)


def estimate(selection: list[dict], analysis: dict, settings: dict) -> dict:
    """selection: [{'id': feature_id, 'complexity': 'S'|'M'|'L'}]"""
    kb = load_kb()
    rows, role_hours = [], {}
    for s in selection:
        f = kb["features"][s["id"]]
        gross = f["hours"] * COMPLEXITY[s["complexity"]]
        mod = kb["module_by_feature"].get(s["id"]) if settings.get("use_modules", True) else None
        saved = gross * mod["reuse_pct"] if mod else 0.0
        net = gross - saved
        rows.append({"id": f["id"], "Feature": f["name"], "Complexity": s["complexity"], "Gross hrs": round(gross),
                     "Reuse": mod["name"] if mod else "-", "Saved hrs": round(saved), "Net hrs": round(net)})
        for role, share in ROLE_MIX[f["category"]].items():
            role_hours[role] = role_hours.get(role, 0) + net * share
    for fx in FIXED_FEATURES:
        rows.append({"id": "fixed", "Feature": fx["name"], "Complexity": "-", "Gross hrs": fx["hours"], "Reuse": "-", "Saved hrs": 0, "Net hrs": fx["hours"]})
        role_hours["DevOps"] = role_hours.get("DevOps", 0) + fx["hours"] * 0.7
        role_hours["Backend"] = role_hours.get("Backend", 0) + fx["hours"] * 0.3

    base = sum(r["Net hrs"] for r in rows)
    nfr_cats = {r["category"] for r in analysis["requirements"] if r["type"] == "Non-functional"}
    mult = round(1 + min(0.1 * len(nfr_cats), 0.3) + (0.1 if "Security & Compliance" in nfr_cats else 0), 3)
    calib = calibration(analysis) if settings.get("use_calibration", True) else 1.0
    buf = risk_buffer(analysis, settings.get("risk_factor", 1.0))
    total = base * mult * calib * (1 + buf)

    scale = total * (1 - PM_SHARE) / (sum(role_hours.values()) or 1)
    roles = {k: round(v * scale) for k, v in role_hours.items()}
    roles["PM / Architect"] = round(total * PM_SHARE)
    phases = [{"Phase": n, "Share": f"{int(p*100)}%", "Hours": round(total * p)} for n, p in PHASES]

    capacity = settings["team_size"] * settings["hours_per_dev_week"] * settings["sprint_weeks"]
    sprints = max(1, math.ceil(total / capacity))
    conf = "High" if buf < 0.2 else "Medium" if buf < 0.3 else "Low"
    return {"rows": rows, "base_hours": round(base), "multiplier": mult, "calibration": calib, "buffer": buf,
            "total_hours": round(total), "low": round(total * 0.88), "high": round(total * 1.25), "phases": phases,
            "roles": roles, "sprints": sprints, "weeks": sprints * settings["sprint_weeks"],
            "cost": round(total * settings["rate"]), "confidence": conf,
            "reuse_saved": sum(r["Saved hrs"] for r in rows)}
