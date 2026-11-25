from src.estimator import estimate
from src.ingestion import list_samples
from src.pipeline import run_analysis

SETTINGS = {"team_size": 4, "hours_per_dev_week": 30, "sprint_weeks": 2, "rate": 1200, "risk_factor": 1.0}


def _est(an):
    sel = [{"id": f["id"], "complexity": "M"} for f in an["features"]]
    return estimate(sel, an, SETTINGS)


def test_all_samples_run():
    for name, text in list_samples().items():
        an = run_analysis(text)
        est = _est(an)
        assert an["requirements"] and an["features"], name
        assert est["total_hours"] > 0 and est["weeks"] > 0


def test_stack_and_modules():
    s = list_samples()
    assert run_analysis(s["Property Management Portal"])["modules"].count("TenantEase Core") == 1
    assert run_analysis(s["Fintech Ai Assistant"])["stack"]["selected"]["id"] == "ai-rag"
    assert "Azure" == __import__("src.diagram", fromlist=["x"]).cloud_of(run_analysis(s["Fintech Ai Assistant"]))


def test_guardrail_flags_java():
    assert any(o["tech"] == "Java" for o in run_analysis(list_samples()["Career Platform Mobile"])["out_of_catalog"])


def test_complexity_changes_estimate():
    an = run_analysis(list_samples()["Property Management Portal"])
    small = estimate([{"id": f["id"], "complexity": "S"} for f in an["features"]], an, SETTINGS)
    large = estimate([{"id": f["id"], "complexity": "L"} for f in an["features"]], an, SETTINGS)
    assert large["total_hours"] > small["total_hours"]
