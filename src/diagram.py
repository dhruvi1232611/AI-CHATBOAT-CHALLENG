"""Generate Mermaid architecture and deployment diagrams from the analysis."""
CLOUD = {
    "AWS": {"cdn": "CloudFront", "lb": "Application Load Balancer", "compute": "ECS Fargate", "db": "RDS PostgreSQL",
            "store": "S3", "queue": "SQS / ElastiCache", "secrets": "Secrets Manager + KMS", "obs": "CloudWatch"},
    "Azure": {"cdn": "Front Door", "lb": "Application Gateway", "compute": "Container Apps / AKS", "db": "Azure Database for PostgreSQL",
              "store": "Blob Storage", "queue": "Service Bus / Redis", "secrets": "Key Vault", "obs": "Azure Monitor"},
}


def cloud_of(analysis: dict) -> str:
    return "Azure" if "azure" in analysis["facts"]["cloud"].lower() else "AWS"


def architecture(stack: dict, ids: set[str], modules: list[str]) -> str:
    c = stack["components"]
    L = ["flowchart LR", '  U(["Users"]) --> FE["%s"]' % c["frontend"], '  FE --> API["%s API"]' % c["backend"],
         '  API --> DB[("%s")]' % c["database"]]
    if "auth" in ids or "multi_tenant" in ids:
        L += ['  API --> AUTH["Auth & RBAC"]']
    if "ai_assistant" in ids or "document_processing" in ids or "career_intel" in ids:
        L += ['  API --> RET["Hybrid retrieval"]', '  RET --> VEC[("%s")]' % c.get("vector", "Qdrant"),
              '  API --> LLM["LLM gateway + guardrails"]']
    if "document_processing" in ids:
        L += ['  API --> OCR["OCR & parsing pipeline"]']
    if ids & {"workflow_automation", "realtime", "notifications"} or "queue" in c or "cache" in c:
        L += ['  API --> Q["Queue / cache"]', '  Q --> W["Background workers"]']
    if ids & {"file_storage", "document_processing"}:
        L += ['  API --> S3[("Object storage")]']
    if "payments" in ids:
        L += ['  API --> PAY["Payment gateway"]']
    if "integrations" in ids:
        L += ['  API --> EXT["External systems (ERP / CRM)"]']
    if "notifications" in ids:
        L += ['  W --> NOTIF["Email / SMS / WhatsApp / Push"]'] if ids & {"workflow_automation", "realtime", "notifications"} else []
    if "mobile_app" in ids:
        L += ['  U --> MOB["Mobile app"]', '  MOB --> API']
    if "geo_maps" in ids:
        L += ['  FE --> MAP["Maps service"]']
    for i, m in enumerate(modules):
        L += [f'  API -.-> M{i}["Reuse: {m}"]']
    L += ["  classDef reuse fill:#e6f4f1,stroke:#0f766e,color:#134e4a;"]
    L += ["  class %s reuse;" % ",".join(f"M{i}" for i in range(len(modules)))] if modules else []
    return "\n".join(L)


def deployment(cloud: str, ids: set[str]) -> str:
    p = CLOUD[cloud]
    L = ["flowchart TB", '  U(["Users"]) --> CDN["%s"]' % p["cdn"], '  CDN --> LB["%s"]' % p["lb"],
         '  subgraph PRIV["Private network (zero-trust)"]', '    LB --> APP["%s: web + API"]' % p["compute"],
         '    APP --> DB[("%s")]' % p["db"], '    APP --> SEC["%s"]' % p["secrets"]]
    if ids & {"file_storage", "document_processing"}:
        L += ['    APP --> ST[("%s")]' % p["store"]]
    if ids & {"workflow_automation", "realtime", "notifications", "ai_assistant"}:
        L += ['    APP --> QU["%s"]' % p["queue"]]
    L += ["  end", '  APP --> OBS["%s"]' % p["obs"]]
    return "\n".join(L)
