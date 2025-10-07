# 🧠 Jira Analyzer

A **fault-tolerant Python project** that automates the fetching, analysis, and visualization of Jira issues — designed to handle interruptions gracefully and resume from where it left off.

This project is divided into two main modules:
- `env_setup/` — initializes a Jira project, generates issues, and uploads them for testing or seeding.
- `analysis/` — fetches real Jira issues, classifies them by technology using an LLM, extracts referenced servers, and visualizes results.

---

## 🧩 Features

### 🧱 1. Fault-Tolerant Fetching
The script in `analysis/fetch_issues.py` connects to the Jira API, retrieves all issues (in pages), and:
- Saves each issue incrementally into a **partial JSONL file**.
- Maintains a **checkpoint file** to resume after crashes or interruptions.
- Automatically deduplicates previously saved issues.
- Produces a final `issues_data.json` for later analysis.

If the script is rerun after an interruption, it picks up exactly where it stopped.

---

### 🔍 2. Intelligent Analysis
`analysis/analyze.py` processes the issues and performs two key analyses:

#### **Server Extraction**
- Detects all server mentions in descriptions (e.g., `srv-db1`, `srv-auth03`, etc.).
- Counts and summarizes how frequently each server appears.
- Outputs:
  - `server_mentions.jsonl` (per issue)
  - `server_counts.jsonl` (aggregate)
  - `unresolved_servers_tickets.json` (issues without any `srv-` mention)

#### **Technology Classification**
- Uses an **LLM (via OpenRouter)** to categorize each issue by its technology domain:
  - `database`, `networking`, `authentication`, `api`, or `storage`.
- Each issue is classified into **exactly one label**.
- Produces:
  - `technology_annotations.jsonl` (per issue)
  - `technology_counts.jsonl` (aggregate)

#### **Fault Tolerance**
Like the fetcher, this analysis is resumable — it detects already-processed issues and skips them on subsequent runs.

---

### 📊 3. Visualization
The `analysis/visualize.py` script reads the aggregated results and produces clear bar charts:

- **Top 15 Servers by Frequency** → `output/server_counts.png`
- **Technology Distribution** → `output/technology_counts.png`

These visualizations help identify which servers or technologies are most commonly referenced in your Jira incidents.

---

### ⚙️ 4. Environment Setup and Initialization
The `env_setup/` package contains helper scripts for:
- Generating synthetic Jira issues for testing (`generate_issues.py`)
- Uploading those issues to your Jira project (`upload_issues.py`)

You can use these tools to create a reproducible dataset if you don’t want to run against production Jira data.

---

## 🗂️ Project Structure

```
home_excersice/
├── analysis/
│   ├── analyze.py              # Main analysis pipeline (server + technology)
│   ├── fetch_issues.py         # Fault-tolerant Jira fetcher
│   ├── visualize.py            # Data visualization
│   └── output/                 # All analysis artifacts and graphs
├── env_setup/
│   ├── generate_issues.py      # Create synthetic Jira issues
│   ├── upload_issues.py        # Upload generated issues to Jira
├── .env                        # (Not tracked) contains credentials and API keys
├── .gitignore
└── README.md
```

---

## 🚀 Usage Guide

### 1️⃣ Configure Environment Variables
Create a `.env` file in the project root with your credentials:

```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your_api_token
OPENROUTER_API_KEY=your_openrouter_key
```

> You can copy `.env.example` as a template (recommended for public repos).

---

### 2️⃣ Fetch Issues (Resumable)
```bash
python analysis/fetch_issues.py --project TON
```
- Saves all issues to:
  - `issues_partial.jsonl` (streamed)
  - `fetch_checkpoint.json` (for resume)
  - `issues_data.json` (final)

If interrupted, just re-run — it continues automatically.

---

### 3️⃣ Analyze and Classify
```bash
python analysis/analyze.py
```
This will:
- Extract servers
- Classify each issue’s technology
- Produce aggregated summaries in `analysis/output/`

---

### 4️⃣ Visualize Results
```bash
python analysis/visualize.py
```
Generates:
- `output/server_counts.png`
- `output/technology_counts.png`

---

## 🧠 Example Output

**Server Extraction Summary**
```
Total issues analyzed: 20000
Issues without any srv-: 354
Unique servers found: 42
```

**Technology Classification Summary**
```
Classified issues: 20000
- api: 10234
- database: 4321
- networking: 2865
- storage: 1221
- authentication: 1359
```

---

## 🧰 Requirements

- Python ≥ 3.10  
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

*(Typical libraries: `requests`, `python-dotenv`, `openai`, `matplotlib`)*

---

## 💡 Highlights
✅ Fault-tolerant at every step  
✅ LLM-powered technology classification  
✅ Automated data visualization  
✅ Resumable from checkpoints  
✅ Designed for both **real** and **synthetic** Jira projects  

---

## 🏁 License
MIT License © 2025 – Developed by Carmel Cohen
