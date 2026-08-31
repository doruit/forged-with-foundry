# Forged with Foundry — AI Governance Controls Demo

A hands-on demo project showcasing **AI Governance Controls** built with **Azure AI Foundry** and the **Azure AI Evaluation SDK**.

---

## 🗂️ Project Structure

The `controls/` folder mirrors the **Governance Signal / Control Repository**
(see [docs/Governance Signals Repo.pdf](docs/Governance%20Signals%20Repo.pdf)).
It is organised in two levels:

- **1st level = Category / domain** (e.g. `security`, `privacy`, `value`, `runtime`)
- **2nd level = Control / signal** (e.g. `SEC-001_prompt_injection_attempts`)

```
forged-with-foundry/
├── controls/
│   ├── security/
│   │   ├── SEC-001_prompt_injection_attempts/README.md
│   │   ├── SEC-002_successful_prompt_injection/README.md
│   │   └── ...
│   ├── privacy/
│   │   ├── PRI-001_pii_exposure/README.md
│   │   └── ...
│   ├── grounding/
│   │   └── QLT-005_citation_support_failure/README.md
│   └── ... (56 categories, 160 controls)
├── scripts/
│   └── scaffold_controls.py   # Regenerates the controls/ structure
├── shared/
│   └── utils.py               # Shared client setup & helpers
├── docs/
│   └── Governance Signals Repo.pdf
├── run_all_demos.py
├── requirements.txt
├── .env.example
└── .gitignore
```

Each control folder contains a `README.md` with its metadata: **ID, lifecycle
phase, evidence/source, trigger/threshold, action/gate effect, and accountable
role**. Add the detection/evaluation implementation inside the relevant control
folder.

### Regenerating the structure

```bash
python scripts/scaffold_controls.py
```

---

## 🛡️ Governance Categories

The repository spans **three lifecycle phases** (Pre-Live, Live, Portfolio) and
**56 categories**, including:

| Category | Example controls |
|---|---|
| **Security** | Prompt injection, data exfiltration, secret exposure |
| **Privacy** | PII exposure, retention violation, personal data in logs |
| **Grounding / Quality** | Low grounding score, hallucination rate, citation support |
| **Runtime** | Escalation spike, agent loops, context contamination |
| **Responsible AI** | Bias indicators, fairness degradation, explainability |
| **Value / FinOps** | KPI underperformance, cost spikes, value leakage |
| **Tool Governance** | Unauthorized tool usage, credential misuse |
| **Compliance / Legal** | Regulatory classification, policy violations, IP risk |

See the individual control READMEs under `controls/` for the full list.


---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/<your-org>/forged-with-foundry.git
cd forged-with-foundry
```

### 2. Set up a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
# Fill in your Azure subscription, resource group and a unique Foundry account name
```

### 5. Deploy the infrastructure (Foundry + GPT-5 models)

Provisions a Microsoft Foundry account, a default project, and the latest GA
GPT-5 models (`gpt-5`, `gpt-5-mini`, `text-embedding-3-large`) via Bicep. The
script writes the resulting endpoints back into `.env`.

```bash
az login          # if not already signed in
./infra/deploy.sh
```

See [infra/README.md](infra/README.md) for details and options.

### 6. Explore a control

Browse `controls/<category>/<control>/README.md` to see each control's metadata,
then add your implementation there. For example:

```bash
cat controls/security/SEC-001_prompt_injection_attempts/README.md
cat controls/grounding/QLT-005_citation_support_failure/README.md
```

### 7. Regenerate the structure (optional)

```bash
python scripts/scaffold_controls.py
```

---

## 📋 Prerequisites

- Azure subscription with access to **Azure AI Foundry**
- Python 3.10+
- **Azure CLI** installed and `az login` completed
- Sufficient **GPT-5 quota** in your chosen region (default `swedencentral`)
