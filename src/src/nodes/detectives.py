# src/nodes/detectives.py
import os
import re
from src.state import AgentState, Evidence
from src.tools import repo_tools, doc_tools, vision_tools

# --- Repo Investigator ---
def repo_investigator(state: AgentState, dimension: dict) -> AgentState:
    try:
        repo_path = repo_tools.clone_repo(state.repo_url)
        commits = repo_tools.extract_git_history(repo_path)

        found = len(commits) > 3
        rationale = dimension["success_pattern"] if found else dimension["failure_pattern"]

        evidence = Evidence(
            goal=dimension["name"],
            found=found,
            content=str(commits),
            location=repo_path,
            rationale=rationale,
            confidence=0.9 if found else 0.5,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state
    except Exception as e:
        evidence = Evidence(
            goal=dimension["name"],
            found=False,
            content=str(e),
            location=state.repo_url,
            rationale="Error cloning or analyzing repo",
            confidence=0.3,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state

# --- Doc Analyst ---
def doc_analyst(state: AgentState, dimension: dict) -> AgentState:
    try:
        chunks = doc_tools.ingest_pdf(state.pdf_path, chunk_size=500)
        keywords = ["Dialectical Synthesis", "Fan-In", "Fan-Out", "Metacognition"]
        results = doc_tools.keyword_search(chunks, keywords)

        found = any(results.values())
        rationale = dimension["success_pattern"] if found else dimension["failure_pattern"]

        evidence = Evidence(
            goal=dimension["name"],
            found=found,
            content=str(results),
            location=state.pdf_path,
            rationale=rationale,
            confidence=0.8 if found else 0.4,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state
    except Exception as e:
        evidence = Evidence(
            goal=dimension["name"],
            found=False,
            content=str(e),
            location=state.pdf_path,
            rationale="Error parsing PDF",
            confidence=0.3,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state

# --- Vision Inspector ---
def vision_inspector(state: AgentState, dimension: dict) -> AgentState:
    try:
        images = vision_tools.extract_images_from_pdf(state.pdf_path)
        classifications = [vision_tools.classify_diagram_flow(img) for img in images]

        found = len(images) > 0
        rationale = dimension["success_pattern"] if found else dimension["failure_pattern"]

        evidence = Evidence(
            goal=dimension["name"],
            found=found,
            content=str(classifications),
            location=state.pdf_path,
            rationale=rationale,
            confidence=0.7 if found else 0.3,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state
    except Exception as e:
        evidence = Evidence(
            goal=dimension["name"],
            found=False,
            content=str(e),
            location=state.pdf_path,
            rationale="Error extracting diagrams",
            confidence=0.3,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state

# --- Host Analysis Accuracy ---
def host_analysis_accuracy(state: AgentState, dimension: dict) -> AgentState:
    try:
        chunks = doc_tools.ingest_pdf(state.pdf_path, chunk_size=500)
        text = " ".join(chunks)
        file_refs = re.findall(r"[A-Za-z0-9_/\\.-]+\.(py|md|pdf|json)", text)

        actual_files = []
        for root, _, files in os.walk("."):
            for f in files:
                actual_files.append(os.path.relpath(os.path.join(root, f), "."))

        missing = [ref for ref in file_refs if ref not in actual_files]
        found = len(missing) == 0
        rationale = dimension["success_pattern"] if found else dimension["failure_pattern"]

        evidence = Evidence(
            goal=dimension["name"],
            found=found,
            content=f"References: {file_refs}, Missing: {missing}",
            location=state.pdf_path,
            rationale=rationale,
            confidence=0.9 if found else 0.5,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state
    except Exception as e:
        evidence = Evidence(
            goal=dimension["name"],
            found=False,
            content=str(e),
            location=state.pdf_path,
            rationale="Error parsing PDF or repo",
            confidence=0.3,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state

# --- State Management Rigor ---
def state_management_rigor(state: AgentState, dimension: dict) -> AgentState:
    try:
        with open("src/state.py", "r", encoding="utf-8") as f:
            content = f.read()
        found = "BaseModel" in content and "TypedDict" in content
        rationale = dimension["success_pattern"] if found else dimension["failure_pattern"]

        evidence = Evidence(
            goal=dimension["name"],
            found=found,
            content="Checked for BaseModel and TypedDict usage",
            location="src/state.py",
            rationale=rationale,
            confidence=0.9 if found else 0.5,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state
    except Exception as e:
        evidence = Evidence(
            goal=dimension["name"],
            found=False,
            content=str(e),
            location="src/state.py",
            rationale="Error reading state.py",
            confidence=0.3,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state

# --- Graph Orchestration ---
def graph_orchestration(state: AgentState, dimension: dict) -> AgentState:
    try:
        with open("src/graph.py", "r", encoding="utf-8") as f:
            content = f.read()
        found = "StateGraph" in content and "add_edge" in content
        rationale = dimension["success_pattern"] if found else dimension["failure_pattern"]

        evidence = Evidence(
            goal=dimension["name"],
            found=found,
            content="Checked for StateGraph orchestration",
            location="src/graph.py",
            rationale=rationale,
            confidence=0.9 if found else 0.5,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state
    except Exception as e:
        evidence = Evidence(
            goal=dimension["name"],
            found=False,
            content=str(e),
            location="src/graph.py",
            rationale="Error reading graph.py",
            confidence=0.3,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state

# --- Safe Tool Engineering ---
def safe_tool_engineering(state: AgentState, dimension: dict) -> AgentState:
    try:
        with open("src/tools/repo_tools.py", "r", encoding="utf-8") as f:
            content = f.read()
        found = "subprocess.run" in content and "check=True" in content
        rationale = dimension["success_pattern"] if found else dimension["failure_pattern"]

        evidence = Evidence(
            goal=dimension["name"],
            found=found,
            content="Checked for safe subprocess usage",
            location="src/tools/repo_tools.py",
            rationale=rationale,
            confidence=0.9 if found else 0.5,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state
    except Exception as e:
        evidence = Evidence(
            goal=dimension["name"],
            found=False,
            content=str(e),
            location="src/tools/repo_tools.py",
            rationale="Error reading repo_tools.py",
            confidence=0.3,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state

# --- Structured Output Enforcement ---
def structured_output_enforcement(state: AgentState, dimension: dict) -> AgentState:
    try:
        files = ["src/state.py", "src/nodes/justice.py"]
        found = True
        for file in files:
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()
                if "BaseModel" not in content and "Evidence" not in content:
                    found = False
        rationale = dimension["success_pattern"] if found else dimension["failure_pattern"]

        evidence = Evidence(
            goal=dimension["name"],
            found=found,
            content="Checked for structured Evidence output",
            location=str(files),
            rationale=rationale,
            confidence=0.9 if found else 0.5,
        )
        state.evidences.setdefault(dimension["id"], []).append(evidence)
        return state
    except Exception as e:
        evidence = Evidence(
            goal=dimension["name"],
            found=False,
            content=str(e),
            location=str(files),
            rationale="Error reading files",
            confidence=0.3
        )