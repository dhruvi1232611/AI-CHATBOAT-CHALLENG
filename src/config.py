"""Central configuration and constants."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KB_DIR = DATA / "knowledge_base"
RFP_DIR = DATA / "sample_rfps"

# Cynbit's six-stage delivery lifecycle and its share of total effort.
PHASES = [
    ("Discovery", 0.08), ("Blueprinting", 0.10), ("Design", 0.12),
    ("Implementation", 0.45), ("Quality Check", 0.15), ("Deployment", 0.10),
]
COMPLEXITY = {"S": 0.6, "M": 1.0, "L": 1.6}
ROLE_MIX = {
    "core": {"Backend": .55, "Frontend": .35, "QA": .10},
    "ui": {"Frontend": .70, "Backend": .20, "QA": .10},
    "ai": {"AI/ML": .55, "Backend": .30, "QA": .15},
    "mobile": {"Mobile": .70, "Backend": .20, "QA": .10},
    "integration": {"Backend": .70, "DevOps": .10, "QA": .20},
    "infra": {"DevOps": .70, "Backend": .20, "QA": .10},
}
PM_SHARE = 0.10          # architect / project management overhead
FIXED_FEATURES = [       # always needed, independent of the RFP
    {"name": "Project setup, CI/CD & environments", "hours": 50},
    {"name": "Zero-trust security baseline & observability", "hours": 40},
]
LLM_PROVIDERS = {"Google Gemini (free tier)": ("gemini", "gemini-2.5-flash"),
                 "Anthropic Claude (paid)": ("anthropic", "claude-sonnet-5-5")}
