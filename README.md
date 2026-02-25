# The Automaton Auditor

A rubric-driven LangGraph system that audits repositories and reports on engineering quality, governance, and reproducibility.

## Features
- **Detective nodes**: Repo Investigator, Doc Analyst, Vision Inspector, Host Analysis Accuracy, etc.
- **Judicial layer**: Prosecutor, Defense, TechLead opinions synthesized by Chief Justice.
- **StateGraph orchestration**: Parallel fan-out/fan-in with explicit edges.
- **Reproducible infrastructure**: uv dependency management, `.env.example`, clean project layout.

## Setup

1. **Clone the repo**
```bash
   git clone https://github.com/your-org/the-automaton-auditor.git
   cd the-automaton-auditor
```

2. **Install dependencies with uv**

```bash
uv sync
```
3. **Configure environment**

- Copy .env.example to .env

- Fill in your own values (API key, repo URL, PDF path)

4. **Run the auditor**

```bash
uv run python -m src.graph
```

### Dependencies
This project requires:
- Python 3.11+
- uv for dependency management
- PyPDF2 for PDF ingestion

Install everything with:
```bash
uv sync
```
## Project Structure
```bash
src/
  state.py          # Typed state definitions (Evidence, JudicialOpinion, AgentState)
  graph.py          # StateGraph orchestration
  nodes/
    detectives.py   # Detective node implementations
    judges.py       # Judicial opinions
    justice.py      # Chief Justice synthesis + report serialization
    aggregator.py   # Evidence aggregation
tools/
  repo_tools.py     # Sandboxed git clone + repo utilities
  doc_tools.py      # Chunked PDF ingestion + keyword search
  vision_tools.py   # Diagram extraction/classification
rubric/
  rubric.json       # Rubric dimensions and success/failure patterns
audit/
  report_onself_generated/  # Generated audit reports
```
## Output

- Final audit report is saved to:
```bash
audit/report_onself_generated/audit_report.md
```