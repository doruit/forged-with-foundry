"""
Scaffolds the governance controls folder structure under `controls/`.

Structure:
    controls/<category-group>/<control-id_slug>/README.md

Data is derived from docs/Governance Signals Repo.pdf
Columns: Lifecycle phase | ID | Category/domain | Control/signal |
         Evidence/source | Trigger/threshold | Action/gate effect | Accountable role
"""

import re
from pathlib import Path

CONTROLS_ROOT = Path(__file__).resolve().parent.parent / "controls"
GENERATED_MARKER = "<!-- generated-control-readme -->"

CATEGORY_GROUPS = {
    "privacy": ("Privacy",),
    "security": ("Security",),
    "grounding_and_quality": ("Grounding", "Quality"),
    "responsible_ai_and_fairness": ("Responsible AI", "Fairness"),
    "data_and_knowledge": (
        "Access Control",
        "Data",
        "Data Quality",
        "Knowledge",
        "Lineage",
        "Retrieval",
    ),
    "runtime_and_operations": ("Observability", "Operations", "Runtime"),
    "autonomy_and_human_oversight": ("Autonomy", "Human Oversight"),
    "tool_governance": ("Tool Governance",),
    "change_release_and_evaluation": (
        "Change",
        "Evaluation",
        "Guardrails",
        "Release",
        "Security Testing",
    ),
    "compliance_legal_and_risk": (
        "Compliance",
        "Legal",
        "Legal-IP",
        "Risk",
        "Risk Acceptance",
        "Risk Trend",
        "Vendor Risk",
    ),
    "value_adoption_and_finops": (
        "Adoption",
        "FinOps",
        "Value",
        "Value Integrity",
        "Value Risk",
    ),
    "architecture_resilience_and_scale": (
        "Architecture",
        "Dependency",
        "Rationalisation",
        "Resilience",
        "Reuse",
        "Scale",
        "Scale Execution",
        "Scale Risk",
    ),
    "lifecycle_and_portfolio_governance": (
        "Cadence",
        "Channels",
        "Closure",
        "Evidence",
        "Governance",
        "Intake",
        "Lifecycle",
        "Model",
        "Ownership",
        "Portfolio Health",
        "Prompt",
        "Retirement",
        "Strategy",
    ),
}

CATEGORY_TO_GROUP = {
    category: group
    for group, categories in CATEGORY_GROUPS.items()
    for category in categories
}

# (phase, id, category, control, evidence, trigger, action, role)
ROWS = [
    # ---------------- PRE-LIVE ----------------
    ("Pre-Live", "INT-001", "Intake", "Use case not registered", "AI registry, intake form", "Any agent/use case outside registry", "Block intake; register use case", "Business Owner"),
    ("Pre-Live", "INT-002", "Intake", "Business owner missing", "AI registry owner field", "No accountable business owner", "Block approval until assigned", "Business Owner"),
    ("Pre-Live", "INT-003", "Intake", "Executive sponsor missing", "Sponsor assignment", "No sponsor for material/high-risk use case", "Escalate for sponsorship", "Transformation Office"),
    ("Pre-Live", "INT-004", "Intake", "Use case scope unclear", "Use case brief, process scope", "Ambiguous process, users or decision boundary", "Clarify scope before design", "Product Owner"),
    ("Pre-Live", "INT-005", "Autonomy", "Autonomy level undefined", "Autonomy classification", "Recommend/decide/act level not documented", "Block risk classification", "AI Governance"),
    ("Pre-Live", "INT-006", "Channels", "Target users/channels undefined", "Requirements, user journeys", "No target user group or channel", "Complete requirements", "PM"),
    ("Pre-Live", "VAL-PRE-001", "Value", "Value hypothesis missing", "Business case, benefits log", "No measurable business hypothesis", "Block approval to proceed", "Business Owner"),
    ("Pre-Live", "VAL-PRE-002", "Value", "KPI baseline missing", "Baseline KPI report", "No baseline or target before build", "Create baseline before approval", "Business Owner"),
    ("Pre-Live", "VAL-PRE-003", "Value", "Benefit attribution model missing", "Value ledger design", "No link between usage and outcome", "Define attribution method", "Value Steering"),
    ("Pre-Live", "VAL-PRE-004", "Value", "Value owner not assigned", "RACI, governance register", "No named owner for benefits", "Assign benefit owner", "Executive Sponsor"),
    ("Pre-Live", "ADP-PRE-001", "Adoption", "Change impact not assessed", "Change impact analysis", "Affected roles/processes unknown", "Complete change assessment", "Change Lead"),
    ("Pre-Live", "ADP-PRE-002", "Adoption", "Enablement plan missing", "Training plan, comms plan", "No enablement before go-live", "Block release or limit pilot", "Change Lead"),
    ("Pre-Live", "RSK-PRE-001", "Risk", "Risk classification missing", "Risk questionnaire", "No risk tier assigned", "Block approval to proceed", "Risk Officer"),
    ("Pre-Live", "RSK-PRE-002", "Risk", "High-risk classification unresolved", "Risk assessment, decision log", "Material/high-risk use case without decision", "Escalate to governance board", "Risk Officer"),
    ("Pre-Live", "RSK-PRE-003", "Risk", "Residual risk acceptance missing", "Risk acceptance record", "Residual risk above tolerance", "Block release or require acceptance", "Executive Sponsor"),
    ("Pre-Live", "RAI-PRE-001", "Responsible AI", "RAI impact assessment missing", "Responsible AI checklist", "Required assessment absent", "Block release readiness", "RAI Lead"),
    ("Pre-Live", "COM-PRE-001", "Compliance", "AI regulatory classification missing", "AI Act/classification record", "No classification or outdated classification", "Block go-live until classified", "Compliance Officer"),
    ("Pre-Live", "COM-PRE-002", "Compliance", "Policy mapping incomplete", "Control register", "Required policies not mapped", "Complete policy mapping", "Compliance Officer"),
    ("Pre-Live", "LEG-PRE-001", "Legal", "Legal review missing", "Legal approval record", "Required review absent", "Block release", "Legal Counsel"),
    ("Pre-Live", "LEG-PRE-002", "Legal-IP", "IP/copyright risk unresolved", "Source/content license review", "Unresolved content, output or licensing risk", "Legal decision or mitigation", "Legal Counsel"),
    ("Pre-Live", "PRI-PRE-001", "Privacy", "DPIA required but missing", "DPIA decision, processing register", "DPIA required and absent", "Block go-live", "DPO"),
    ("Pre-Live", "PRI-PRE-002", "Privacy", "Lawful basis or purpose missing", "Privacy assessment", "Personal data use without basis/purpose", "Remediate design", "Privacy Officer"),
    ("Pre-Live", "PRI-PRE-003", "Privacy", "Retention design missing", "Retention schedule, logging design", "No retention rule for prompts/logs/data", "Define retention before release", "Privacy Officer"),
    ("Pre-Live", "DAT-PRE-001", "Data", "Data source inventory incomplete", "Data source register", "Unapproved/unknown data source", "Complete inventory", "Data Lead"),
    ("Pre-Live", "DAT-PRE-002", "Data", "Data classification missing", "Classification labels, Purview/DLP", "Unknown data sensitivity", "Classify before use", "Data Owner"),
    ("Pre-Live", "DAT-PRE-003", "Data Quality", "Data quality below threshold", "Data quality rules, profiling report", "Critical data quality < agreed threshold", "Remediate before test/release", "Data Steward"),
    ("Pre-Live", "DAT-PRE-004", "Lineage", "Data lineage incomplete", "Lineage map, source-to-output trace", "Critical data lineage gap", "Fix lineage before sign-off", "Data Owner"),
    ("Pre-Live", "KNW-PRE-001", "Knowledge", "Knowledge owner missing", "Knowledge source register", "No owner for governed source", "Assign owner", "Knowledge Owner"),
    ("Pre-Live", "KNW-PRE-002", "Knowledge", "Source authority hierarchy missing", "Source policy, source ranking", "Conflicting sources without hierarchy", "Define source precedence", "Knowledge Owner"),
    ("Pre-Live", "ARC-PRE-001", "Architecture", "Architecture approval missing", "Architecture decision record", "No architecture sign-off", "Block build", "Chief Architect"),
    ("Pre-Live", "ARC-PRE-002", "Architecture", "Integration pattern not approved", "Solution design, integration catalogue", "Non-standard or unapproved integration", "Architecture review", "Solution Architect"),
    ("Pre-Live", "ARC-PRE-003", "Resilience", "Resilience/rollback design missing", "NFRs, rollback plan", "No fallback, rollback or degraded-mode design", "Block release readiness", "Solution Architect"),
    ("Pre-Live", "SEC-PRE-001", "Security", "Threat model missing", "Threat model, STRIDE/attack paths", "Required threat model absent", "Block release", "Security Architect"),
    ("Pre-Live", "SEC-PRE-002", "Security", "Least-privilege model not approved", "RBAC, PIM, access review", "Excessive/unapproved permissions", "Reduce or approve access", "Security Officer"),
    ("Pre-Live", "SEC-PRE-003", "Security", "Secret management design missing", "Key vault, managed identity design", "Secrets in code/config or unclear custody", "Fix secret management", "Platform Owner"),
    ("Pre-Live", "TOOL-PRE-001", "Tool Governance", "Tool inventory incomplete", "Tool catalogue, API inventory", "Tool/action missing from approved inventory", "Register tool", "Agent Owner"),
    ("Pre-Live", "TOOL-PRE-002", "Tool Governance", "Tool risk tier not approved", "Tool risk assessment", "High-impact tool without approval", "Block tool access", "Security Officer"),
    ("Pre-Live", "AUT-PRE-001", "Autonomy", "Autonomy boundary undefined", "Autonomy policy, action matrix", "No clear allowed/prohibited actions", "Define autonomy boundary", "AI Governance"),
    ("Pre-Live", "AUT-PRE-002", "Human Oversight", "HITL gates missing", "Approval workflow design", "Material action has no human gate", "Block release", "Business Owner"),
    ("Pre-Live", "MOD-PRE-001", "Model", "Model not approved", "Approved model catalogue", "Model/vendor outside approved catalogue", "Replace or submit exception", "AI Engineering Lead"),
    ("Pre-Live", "MOD-PRE-002", "Model", "Model version/configuration missing", "Model card, config record", "No model version, region, settings or fallback", "Complete model record", "AI Engineering Lead"),
    ("Pre-Live", "PRM-PRE-001", "Prompt", "Prompt versioning missing", "Prompt repository, version history", "No version, owner or change history", "Implement prompt governance", "AI Engineering Lead"),
    ("Pre-Live", "PRM-PRE-002", "Prompt", "Prompt safety review missing", "Prompt review checklist", "No test for unsafe instructions or policy conflicts", "Run prompt review", "RAI Lead"),
    ("Pre-Live", "EVAL-PRE-001", "Evaluation", "Evaluation set missing", "Evaluation dataset, acceptance criteria", "No representative eval set", "Block test approval", "QA Lead"),
    ("Pre-Live", "EVAL-PRE-002", "Evaluation", "Required test coverage gap", "Test plan, scenario coverage", "Critical scenarios not covered", "Extend test suite", "QA Lead"),
    ("Pre-Live", "EVAL-PRE-003", "Fairness", "Bias/fairness test missing", "Fairness evaluation evidence", "Required test absent for impacted users", "Run fairness evaluation", "RAI Lead"),
    ("Pre-Live", "EVAL-PRE-004", "Security Testing", "Red-team/prompt-injection test missing", "Adversarial test evidence", "No adversarial testing for exposed agent", "Run red-team tests", "Security Officer"),
    ("Pre-Live", "OPS-PRE-001", "Observability", "Monitoring not configured", "Telemetry, traces, dashboards", "Missing run traces, eval telemetry or alerts", "Block go-live", "Ops Lead"),
    ("Pre-Live", "OPS-PRE-002", "Operations", "Incident runbook missing", "Runbook, escalation matrix", "No incident workflow before launch", "Block go-live", "Ops Manager"),
    ("Pre-Live", "FIN-PRE-001", "FinOps", "Cost model or budget missing", "Cost forecast, budget owner", "No budget, unit economics or limit", "Block scale/go-live decision", "FinOps Lead"),
    ("Pre-Live", "REL-PRE-001", "Release", "Release evidence pack incomplete", "Release checklist, evidence register", "Missing test/risk/privacy/security/value evidence", "Block go-live", "Release Board"),
    ("Pre-Live", "REL-PRE-002", "Release", "Go-live approval missing", "Go/No-Go decision log", "No approved release decision", "Do not release", "Business Owner"),
    # ---------------- LIVE ----------------
    ("Live", "VAL-001", "Value", "KPI underperformance", "KPI vs target dashboard", "<80% target for 2 periods", "Value review", "Business Owner"),
    ("Live", "VAL-002", "Value", "Benefits realisation gap", "Realised vs planned value", "<50% realised after 6 months", "Reassess hypothesis", "Business Owner"),
    ("Live", "VAL-003", "Value", "ROI degradation", "Expected vs actual ROI", ">25% negative deviation", "Portfolio review", "Executive Sponsor"),
    ("Live", "VAL-004", "Value", "Value leakage", "Planned vs captured benefit", ">30% gap", "Root-cause review", "Business Owner"),
    ("Live", "VAL-005", "Value", "Adoption-to-value conversion gap", "Usage vs KPI impact", "High usage with no measurable outcome", "Redesign value model", "Value Steering"),
    ("Live", "ADP-001", "Adoption", "Adoption rate low", "Active users / target users", "<40% adoption", "Adoption intervention", "Change Lead"),
    ("Live", "ADP-002", "Adoption", "Adoption decline", "30-day active users", ">20% decline", "Review journey/training", "Change Lead"),
    ("Live", "ADP-003", "Adoption", "Manual bypass rate high", "Manual bypass rate", ">30% bypass", "Process review", "Product Owner"),
    ("Live", "ADP-004", "Adoption", "Negative satisfaction", "User satisfaction score", "<3.5/5", "UX/service review", "Product Owner"),
    ("Live", "ADP-005", "Adoption", "Low repeat usage", "Repeat users / first-time users", "<30% repeat after 30 days", "Adoption diagnosis", "Change Lead"),
    ("Live", "RUN-001", "Runtime", "Low confidence or grounding score", "Confidence/grounding score", "<70% or below policy band", "Trigger human review", "Agent Owner"),
    ("Live", "RUN-002", "Runtime", "Escalation spike", "Escalation rate", ">15% or >baseline +20%", "Workflow review", "AI Ops Lead"),
    ("Live", "RUN-003", "Runtime", "Autonomous action failure", "Failed autonomous actions", ">2% or 1 critical failure", "Pause autonomy", "AI Ops Lead"),
    ("Live", "RUN-004", "Runtime", "Decision override rate high", "Human overrides / decisions", ">25%", "Review decision logic", "Product Owner"),
    ("Live", "RUN-005", "Runtime", "Unexpected workflow path", "Run trace anomaly", "1 critical unknown path", "Investigate", "AI Ops Lead"),
    ("Live", "RUN-006", "Runtime", "Agent loop or retry storm", "Repeated tool/model calls", ">N retries or cost spike threshold", "Stop run; inspect logic", "AI Ops Lead"),
    ("Live", "RUN-007", "Runtime", "Context contamination", "Session/context boundary checks", "1 confirmed cross-user/session leak", "Incident response", "Security Officer"),
    ("Live", "RUN-008", "Runtime", "Memory misuse or stale memory", "Memory retrieval and age", "Unauthorized, irrelevant or expired memory used", "Disable/fix memory", "Agent Owner"),
    ("Live", "AUT-001", "Autonomy", "HITL bypass", "Action log vs approval matrix", "1 occurrence", "Pause autonomy; incident review", "Ops Manager"),
    ("Live", "AUT-002", "Autonomy", "Irreversible action attempted", "Delete/submit/approve/publish/pay action log", "1 unauthorized attempt", "Block action; escalate", "Ops Manager"),
    ("Live", "AUT-003", "Autonomy", "Autonomy escalation without approval", "Autonomy config change", "Recommend->act or act->execute without approval", "Rollback and review", "AI Governance"),
    ("Live", "TOOL-001", "Tool Governance", "Unauthorized tool usage", "Tool call logs", "1 tool outside allowed scope", "Block tool; investigate", "Security Officer"),
    ("Live", "TOOL-002", "Tool Governance", "Tool failure rate high", "Tool call success rate", ">2% technical failure or SLA breach", "Fix integration", "Technical Owner"),
    ("Live", "TOOL-003", "Tool Governance", "Excessive tool calls", "Tool calls per task", ">approved call budget", "Optimize workflow", "AI Ops Lead"),
    ("Live", "TOOL-004", "Tool Governance", "Tool credential misuse", "Credential and service principal logs", "1 anomalous use", "Rotate credentials; incident response", "Security Officer"),
    ("Live", "QLT-001", "Quality", "Hallucination rate high", "Validated hallucinations", ">5% or critical hallucination", "Quality review", "Product Owner"),
    ("Live", "QLT-002", "Quality", "Answer accuracy low", "Accuracy score", "<85% on validation set", "Improve grounding/model", "Product Owner"),
    ("Live", "QLT-003", "Quality", "Task completion rate low", "Completed tasks / attempts", "<90% or below target", "Review implementation", "Product Owner"),
    ("Live", "QLT-004", "Quality", "Recommendation acceptance low", "Accepted recommendations", "<25%", "Review usefulness", "Business Owner"),
    ("Live", "QLT-005", "Grounding", "Citation support failure", "Citation correctness review", "<95% support for critical answers", "Fix retrieval/citation logic", "Knowledge Owner"),
    ("Live", "QLT-006", "Evaluation", "Production evaluation regression", "Online eval vs baseline", ">5-10% regression", "Open change/release cycle", "QA Lead"),
    ("Live", "KNW-001", "Knowledge", "Knowledge freshness breach", "Source age by source type", "Outside source-specific freshness policy", "Content review", "Knowledge Owner"),
    ("Live", "KNW-002", "Knowledge", "Unanswered rate high", "No-answer / fallback rate", ">10%", "Knowledge gap review", "Knowledge Owner"),
    ("Live", "KNW-003", "Knowledge", "Source conflict detected", "Conflicting source ratio", ">5% or 1 critical policy conflict", "Resolve source hierarchy", "Knowledge Owner"),
    ("Live", "KNW-004", "Retrieval", "Retrieval relevance low", "Top-k relevance score", "Below approved threshold", "Tune index/retriever", "AI Engineering Lead"),
    ("Live", "KNW-005", "Access Control", "Permission trimming failure", "Retrieved docs vs user permissions", "1 occurrence", "Incident response", "Security Officer"),
    ("Live", "SEC-001", "Security", "Prompt injection attempts", "Security detector events", ">10/day or anomalous campaign", "Security review", "Security Officer"),
    ("Live", "SEC-002", "Security", "Successful prompt injection", "Confirmed policy/tool/data bypass", "1 occurrence", "Incident response; patch guardrails", "SOC"),
    ("Live", "SEC-003", "Security", "Unauthorized access", "Access violation", "1 occurrence", "Block and investigate", "Security Officer"),
    ("Live", "SEC-004", "Security", "Data exfiltration attempt", "DLP alert / egress event", "1 occurrence", "Incident response", "Security Officer"),
    ("Live", "SEC-005", "Security", "Secret exposure", "Secret scanning in prompt/response/logs", "1 occurrence", "Rotate secret; incident response", "Security Officer"),
    ("Live", "SEC-006", "Security", "Abnormal usage pattern", "Usage, token, geo, auth anomaly", "Outside behavioural baseline", "Investigate", "SOC"),
    ("Live", "SEC-007", "Security", "Supply chain vulnerability", "Dependency/package/image scan", "Critical vuln in runtime path", "Patch or isolate", "Platform Owner"),
    ("Live", "PRI-001", "Privacy", "PII exposure", "DLP/content safety event", "1 occurrence", "Immediate escalation", "Privacy Officer"),
    ("Live", "PRI-002", "Privacy", "Retention violation", "Retention checks", "1 exception", "Remediate/delete", "Privacy Officer"),
    ("Live", "PRI-003", "Privacy", "Data subject request SLA breach", "DSR SLA tracking", "Missed SLA", "Escalate", "DPO"),
    ("Live", "PRI-004", "Privacy", "Personal data in logs", "Log inspection/DLP", "Unexpected personal data in logs", "Mask/delete; update logging", "Privacy Officer"),
    ("Live", "COM-001", "Compliance", "Regulatory/control failure", "Control assessment", "1 failed critical control", "Remediate or pause", "Compliance Officer"),
    ("Live", "COM-002", "Compliance", "Critical audit finding", "Open audit findings", ">0 critical", "Action plan", "Compliance Officer"),
    ("Live", "COM-003", "Compliance", "Policy violation", "Policy engine result", "1 policy breach", "Investigate", "Compliance Officer"),
    ("Live", "COM-004", "Compliance", "Operational log retention gap", "Log retention evidence", "Logs unavailable before minimum retention", "Fix retention; assess impact", "Compliance Officer"),
    ("Live", "RAI-001", "Responsible AI", "Bias indicator outside approved band", "Bias/fairness tests", "Outside approved band", "Responsible AI review", "RAI Lead"),
    ("Live", "RAI-002", "Responsible AI", "Fairness degradation", "Fairness metric vs baseline", ">10% degradation", "Review model/data", "RAI Lead"),
    ("Live", "RAI-003", "Responsible AI", "Explainability gap", "Explainable decisions ratio", "<90% for governed decisions", "Review explanation mechanism", "RAI Lead"),
    ("Live", "OPS-001", "Operations", "Availability degradation", "Availability/SLA", "<99% or agreed SLO", "Operational review", "Platform Owner"),
    ("Live", "OPS-002", "Operations", "Latency increase", "p95 response time", ">5 sec or agreed SLO breach", "Performance tuning", "Platform Owner"),
    ("Live", "OPS-003", "Operations", "Technical failure rate high", "Failure rate", ">2%", "Incident review", "AI Ops Lead"),
    ("Live", "OPS-004", "Operations", "Dependency failure", "External dependency availability", ">3 consecutive failures or >4h outage", "Escalate; continuity plan", "Platform Owner"),
    ("Live", "OPS-005", "Operations", "Rate-limit saturation", "Quota/rate-limit telemetry", ">80% sustained or hard throttle", "Capacity action", "Platform Owner"),
    ("Live", "OPS-006", "Observability", "Missing run trace", "Trace completeness", "<100% for critical runs", "Fix telemetry", "Ops Lead"),
    ("Live", "FIN-001", "FinOps", "Cost spike", "Monthly cost trend", ">30% above rolling average", "FinOps review", "FinOps Lead"),
    ("Live", "FIN-002", "FinOps", "Cost per outcome above plan", "Cost / successful outcome", ">20% above plan", "Optimize model/tool flow", "FinOps Lead"),
    ("Live", "FIN-003", "FinOps", "Budget consumption high", "Budget used", ">90% before period end", "Approval review", "Executive Sponsor"),
    ("Live", "FIN-004", "FinOps", "Retry-loop cost leakage", "Cost per failed run / retries", ">threshold or anomaly", "Stop loop; fix logic", "AI Ops Lead"),
    ("Live", "CHG-001", "Change", "Unapproved prompt change", "Prompt repo vs prod config", "Any unapproved prod change", "Rollback or approve", "AI Engineering Lead"),
    ("Live", "CHG-002", "Change", "Model version changed without regression test", "Model config/change log", "Any prod version change without eval", "Rollback; run eval", "AI Engineering Lead"),
    ("Live", "CHG-003", "Change", "Knowledge source changed without validation", "Indexing/source change log", "Critical source changed without validation", "Revalidate retrieval", "Knowledge Owner"),
    ("Live", "CHG-004", "Guardrails", "Guardrail regression", "Safety/policy eval score", ">5% degradation or 1 critical bypass", "Patch guardrails", "RAI"),
    ("Live", "LIF-001", "Lifecycle", "Owner unavailable or changed", "RACI, HR/source owner check", "No active accountable owner", "Assign successor", "Business Owner"),
    ("Live", "LIF-002", "Lifecycle", "Periodic review overdue", "Review schedule", "Past due", "Trigger operational review", "Agent Owner"),
    # ---------------- PORTFOLIO ----------------
    ("Portfolio", "PRT-001", "Strategy", "Strategic opportunity not assessed", "Strategic objectives vs AI opportunity log", "Critical objective not assessed", "Discovery workshop", "AI Portfolio Lead"),
    ("Portfolio", "PRT-002", "Strategy", "KPI coverage gap", "Critical KPIs vs use cases", "Critical KPI has no assessed use case", "Portfolio review", "Value Steering"),
    ("Portfolio", "PRT-003", "Rationalisation", "Duplicate capability", "Agent capabilities map", ">3 agents solving same problem", "Rationalisation review", "Architecture Board"),
    ("Portfolio", "PRT-004", "Reuse", "Reuse opportunity identified", "Capability similarity, reuse score", "Cross-domain applicability found", "Scale/reuse proposal", "AI Portfolio Lead"),
    ("Portfolio", "PRT-005", "Ownership", "Orphaned agent/use case", "Registry owner/sponsor fields", "No owner or sponsor", "Assign, pause or retire", "Portfolio Board"),
    ("Portfolio", "PRT-006", "Portfolio Health", "Portfolio health degradation", "Aggregate risk/value/adoption dashboard", "Worsening trend over 2 periods", "Portfolio intervention", "Portfolio Board"),
    ("Portfolio", "VAL-PORT-001", "Value", "Aggregate value below plan", "Portfolio realised vs planned value", "<70% planned value realised", "Reprioritise investments", "Value Steering"),
    ("Portfolio", "VAL-PORT-002", "Value Risk", "Value concentration risk", "Value by agent/domain", "Top agent/domain carries excessive value dependency", "Resilience/redundancy plan", "Executive Sponsor"),
    ("Portfolio", "VAL-PORT-003", "Value Integrity", "Duplicate benefit claim", "Benefit ledger / finance validation", "Same benefit claimed by multiple agents", "Resolve attribution", "Finance"),
    ("Portfolio", "VAL-PORT-004", "Value", "High usage, low value agent", "Usage vs KPI impact", "High active use with weak/no outcome", "Redesign or retirement review", "Business Owner"),
    ("Portfolio", "SCL-001", "Scale", "Scale readiness evidence missing", "Scale readiness pack", "Missing value, risk, ops, adoption or compliance evidence", "Block scale approval", "Steering Committee"),
    ("Portfolio", "SCL-002", "Scale", "Scale candidate under-documented", "Pilot-to-scale evidence", "Pilot lacks quantified results or risk evidence", "Extend pilot", "AI Portfolio Lead"),
    ("Portfolio", "SCL-003", "Scale Risk", "Scale blocked by compliance/risk", "Open critical controls", "Any unresolved critical control", "Do not scale", "Compliance"),
    ("Portfolio", "SCL-004", "Scale Execution", "Scale execution lag", "Scale plan milestones", ">20% milestone slippage", "Escalate delivery plan", "Solution Lead"),
    ("Portfolio", "RAT-001", "Rationalisation", "Overlapping investments", "Backlog/funding map", "Multiple funded initiatives for same capability", "Merge or stop work", "Portfolio Board"),
    ("Portfolio", "RAT-002", "Rationalisation", "Low-value long tail", "Cost, usage, support load", "Low usage/value with ongoing cost", "Retirement candidate", "FinOps"),
    ("Portfolio", "RAT-003", "Reuse", "Reusable asset not adopted", "Reuse catalogue vs new builds", "Teams rebuild approved capability", "Enforce reuse or exception", "Architecture Board"),
    ("Portfolio", "RAT-004", "Architecture", "Component sprawl", "Components, models, patterns count", "Uncontrolled variation across teams", "Standardisation review", "Chief Architect"),
    ("Portfolio", "FIN-PORT-001", "FinOps", "Portfolio cost growth exceeds value growth", "Cost growth vs value growth", "Cost grows > value for 2 periods", "Investment review", "FinOps Lead"),
    ("Portfolio", "FIN-PORT-002", "FinOps", "Unit cost variance by team/domain", "Cost per outcome by team", ">30% unexplained variance", "Benchmark/optimize", "FinOps Lead"),
    ("Portfolio", "FIN-PORT-003", "FinOps", "Idle capacity or unused licences", "Utilisation/licence telemetry", "Unused >30/60 days or below utilisation band", "Rightsize/reallocate", "Platform Owner"),
    ("Portfolio", "RSK-PORT-001", "Risk", "High-risk concentration", "Risk tier distribution", "Too many high-risk agents in one domain/platform", "Risk concentration review", "Risk Officer"),
    ("Portfolio", "RSK-PORT-002", "Dependency", "Critical dependency concentration", "Dependency map", "Multiple critical agents rely on single weak point", "Resilience plan", "Platform Owner"),
    ("Portfolio", "RSK-PORT-003", "Risk Trend", "Cross-agent incident trend", "Incident trend by category", ">20% increase or repeated category", "Systemic risk review", "Risk Officer"),
    ("Portfolio", "RSK-PORT-004", "Vendor Risk", "Vendor/model risk escalation", "Vendor notices, SLA/security ratings", "Critical vendor notice or SLA trend", "Vendor risk review", "Procurement"),
    ("Portfolio", "GOV-PORT-001", "Governance", "Registry completeness gap", "AI registry completeness score", "<100% critical fields for live agents", "Clean-up campaign", "Transformation Office"),
    ("Portfolio", "GOV-PORT-002", "Governance", "Unresolved open controls", "Control register", "Critical controls overdue", "Escalate to board", "Compliance Officer"),
    ("Portfolio", "GOV-PORT-003", "Risk Acceptance", "Overdue risk acceptance review", "Risk acceptance expiry dates", "Expired acceptance", "Renew, reduce or retire", "Risk Officer"),
    ("Portfolio", "GOV-PORT-004", "Evidence", "Evidence quality gap", "Evidence completeness/quality score", "Missing or unverifiable evidence", "Remediate evidence register", "Governance Office"),
    ("Portfolio", "ARC-PORT-001", "Architecture", "Architecture drift", "Architecture conformance checks", "Unapproved pattern deviation", "Architecture review", "Chief Architect"),
    ("Portfolio", "ARC-PORT-002", "Architecture", "Common capability missing", "Capability heatmap", "Repeated bespoke implementations", "Create reusable platform capability", "Architecture Board"),
    ("Portfolio", "RET-001", "Retirement", "Unused agent retirement candidate", "Usage telemetry", "No meaningful use for 60 days", "Retirement review", "Business Owner"),
    ("Portfolio", "RET-002", "Retirement", "Business owner requests retirement", "Owner request / service review", "Formal owner request", "Approve retirement plan", "Business Owner"),
    ("Portfolio", "RET-003", "Retirement", "Model/vendor deprecation", "Vendor/model notice", "Deprecation within migration window", "Migration or retirement plan", "Technical Owner"),
    ("Portfolio", "RET-004", "Closure", "Archival evidence incomplete", "Closure checklist, evidence archive", "Missing logs, approvals, risk closure or data deletion evidence", "Block closure", "Compliance Officer"),
    ("Portfolio", "RET-005", "Closure", "Retired agent still accessible", "Access/runtime inventory", "Retired endpoint/tool remains active", "Disable and investigate", "Ops Manager"),
    ("Portfolio", "MTR-001", "Cadence", "Governance cadence missed", "Meeting calendar, decision logs", "Portfolio board or review missed", "Reschedule/escalate", "Transformation Office"),
    ("Portfolio", "MTR-002", "Cadence", "KPI/value review missed", "Review schedule, value dashboard", "Value review overdue", "Trigger review", "Value Steering"),
]


def slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[/\\]", "-", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def control_readme(
    phase: str,
    cid: str,
    category: str,
    control: str,
    evidence: str,
    trigger: str,
    action: str,
    role: str,
) -> str:
    """Return the standard documentation skeleton for a planned control demo."""
    return f"""{GENERATED_MARKER}
<p align="center">
    <img src="../../../media/themepack/fwf-badge-small-only-logo.png" alt="Forged with Foundry planned control" width="223">
</p>

# {cid} — {control}

> **Status:** Planned — the demo has not been implemented yet.
>
> **Last reviewed:** Not yet reviewed; set a date when implementation begins.

Remove the `generated-control-readme` marker when implementation begins so
future catalog regeneration preserves this README.

## Overview

This control detects **{control.lower()}** during the **{phase}** lifecycle
phase. This page will evolve with the implementation while retaining the
standard control documentation structure.

## Control contract

| Field | Value |
|---|---|
| **ID** | {cid} |
| **Lifecycle phase** | {phase} |
| **Category / domain** | {category} |
| **Control / signal** | {control} |
| **Evidence / source** | {evidence} |
| **Trigger / threshold** | {trigger} |
| **Action / gate effect** | {action} |
| **Accountable role** | {role} |

## Control objective

Document the risk addressed by this control, the expected outcome, and why the
control must remain deterministic and independently enforceable where relevant.

## Logical design

```mermaid
flowchart LR
    I[Governed input or evidence] --> D[Detection and evaluation]
    D --> P{{{cid} policy decision}}
    P -->|Below threshold| A[Allow or continue]
    P -->|Threshold reached| E[Apply gate effect]
    E --> O[Notify {role}]

    classDef governance fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
    classDef platform fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
    classDef success fill:#22C55E,stroke:#22C55E,color:#0D1117
    classDef attention fill:#F59E0B,stroke:#F59E0B,color:#0D1117
    class D,P governance
    class I platform
    class A success
    class E,O attention
```

## Infrastructure architecture

```mermaid
flowchart TB
    S[Signal or evidence source] --> C[Control evaluator]
    C --> R[Decision and audit record]
    R --> G[Governance action or gate]
    G --> M[Monitoring and accountable role]

    classDef governance fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
    classDef platform fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
    classDef evidence fill:#00D4FF,stroke:#3B82F6,color:#0D1117
    classDef neutral fill:#1F2937,stroke:#6E56CF,color:#FFFFFF
    classDef attention fill:#F59E0B,stroke:#F59E0B,color:#0D1117
    class S neutral
    class C platform
    class R evidence
    class G governance
    class M attention
```

The implementation must replace this conceptual diagram with the actual Azure,
Microsoft Foundry, storage, identity, monitoring, and integration components.

## Implementation

### Components

- **Detector/evaluator:** To be implemented.
- **Policy decision:** To be implemented from the control contract above.
- **Action or gate:** To be implemented.
- **Audit evidence:** To be implemented without exposing sensitive payloads.

### Best-practice requirements

- Keep policy enforcement outside model reasoning when a deterministic control
  is possible.
- Use least-privilege identity and secretless authentication where supported.
- Minimize retained data and exclude sensitive values from logs and alerts.
- Fail closed when a mandatory control cannot complete safely.
- Pin or document API/model versions and review them during repository updates.

## Demo

### Prerequisites

To be documented with the implementation.

### Run

To be documented with the implementation.

### Expected scenarios

| Scenario | Expected result |
|---|---|
| Below threshold | Control allows processing or records a healthy signal. |
| Threshold reached | Control applies **{action}** and routes accountability to **{role}**. |
| Evaluation unavailable | Mandatory enforcement fails closed or follows the documented fallback. |

## Evidence and observability

Document emitted metrics, traces, audit records, alert payloads, retention, and
the evidence required to prove that the control operated as designed.

## Security and privacy

Document threat boundaries, RBAC, managed identities, network/data flows,
sensitive-data handling, cleanup, and failure behavior.

## Validation

Document automated tests, manual demo checks, expected results, and known
limitations.

## Cleanup

Document control-specific cleanup steps and identify shared resources that must
not be deleted accidentally.

## References

- Add links to the latest authoritative Microsoft Learn documentation used by
  the implementation.
- Source catalog: [Governance Signals Repo.pdf](../../../docs/Governance%20Signals%20Repo.pdf)

---

<p align="center">
    <img src="../../../media/themepack/fwf-footer.png" alt="Forged with Foundry" width="814">
</p>
"""


def build():
    count = 0
    for phase, cid, category, control, evidence, trigger, action, role in ROWS:
        group_dir = CONTROLS_ROOT / CATEGORY_TO_GROUP[category]
        control_dir = group_dir / f"{cid}_{slug(control)}"
        control_dir.mkdir(parents=True, exist_ok=True)

        readme = control_dir / "README.md"
        current = readme.read_text(encoding="utf-8") if readme.exists() else ""
        is_legacy_placeholder = "TODO: Implement the detection/evaluation logic" in current
        if not current or current.startswith(GENERATED_MARKER) or is_legacy_placeholder:
            readme.write_text(
                control_readme(
                    phase, cid, category, control, evidence, trigger, action, role
                ),
                encoding="utf-8",
            )
        else:
            print(f"Preserved implemented control: {cid}")
        count += 1

    print(f"Created {count} controls across {len(CATEGORY_GROUPS)} category groups:")
    for group in CATEGORY_GROUPS:
        n = len(list((CONTROLS_ROOT / group).glob("*/README.md")))
        print(f"  - {group} ({n})")


if __name__ == "__main__":
    build()
