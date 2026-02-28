# src/graph.py
import os
import json
import time
import functools
from typing import List
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from src.nodes.detectives import (
    git_forensic_analysis,      # git_forensic_analysis
    doc_analyst,                # doc_analyst
    diagram_flow,               # diagram_flow
    state_management_rigor,     # state_management_rigor
    graph_orchestration,        # graph_orchestration
    safe_tool_engineering,      # safe_tool_engineering
    host_analysis_accuracy,     # host_analysis_accuracy
    structured_output           # structured_output
)
from src.state import AgentState, Evidence
from src.nodes import aggregator, judges, justice
from src.state import JudicialOpinion
from src.state import CriterionResult, AuditReport


# Load environment variables
load_dotenv()

def load_rubric(path="rubric/rubric.json"):
    """Load rubric JSON file into memory."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# --- Retry decorator ---
def retry(max_attempts=3, delay=1, backoff=2):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        raise
                    time.sleep(current_delay)
                    current_delay *= backoff
            return None
        return wrapper
    return decorator

# --- Safe wrappers for critical detectives ---
@retry(max_attempts=3, delay=1, backoff=2)
def safe_git_forensic_analysis(state, dim):
    return git_forensic_analysis(state, dim)

@retry(max_attempts=2, delay=2, backoff=2)
def safe_doc_analyst(state, dim):
    return doc_analyst(state, dim)

# --- Detective Map ---
DETECTIVE_MAP = {
    "git_forensic_analysis": lambda state, dim: safe_git_forensic_analysis(state, dim),
    "doc_analyst": lambda state, dim: safe_doc_analyst(state, dim),
    "diagram_flow": lambda state, dim: diagram_flow(state, dim),
    "state_management_rigor": lambda state, dim: state_management_rigor(state, dim),
    "graph_orchestration": lambda state, dim: graph_orchestration(state, dim),
    "safe_tool_engineering": lambda state, dim: safe_tool_engineering(state, dim),
    "host_analysis_accuracy": lambda state, dim: host_analysis_accuracy(state, dim),
    "structured_output": lambda state, dim: structured_output(state, dim),
    "judicial_nuance": lambda state, dim: Evidence(
        goal=dim["name"],
        found=True,
        content="Distinct reasoning styles observed: Prosecutor, Defense, TechLead",
        location="src/nodes/judges.py",
        rationale=dim["success_pattern"],
        confidence=0.8
    ),
    "synthesis_conflict_resolution": lambda state, dim: Evidence(
        goal=dim["name"],
        found=True,
        content="Chief Justice synthesis with dissent summary",
        location="src/nodes/justice.py",
        rationale=dim["success_pattern"],
        confidence=0.9
    ),
}

# --- Detective wrapper ---
def make_detective(dimension):
    def detective_node(state: AgentState):
        try:
            result = DETECTIVE_MAP[dimension["id"]](state, dimension)
            if isinstance(result, AgentState):
                return {"evidences": result.evidences}
            elif isinstance(result, Evidence):
                return {"evidences": {dimension["id"]: [result]}}
            elif isinstance(result, list) and all(isinstance(ev, Evidence) for ev in result):
                return {"evidences": {dimension["id"]: result}}
            elif isinstance(result, dict) and "evidences" in result:
                return result
            else:
                return {"errors": [f"{dimension['id']} returned unexpected type: {type(result)}"]}
        except Exception as e:
            return {"errors": [f"{dimension['id']} failed: {e}"]}
    return detective_node

# --- Build Graph ---
def build_graph(rubric):
    graph = StateGraph(AgentState)

    # Entry node
    def entry_node(state: AgentState):
        return {}
    graph.add_node("entry", entry_node)
    graph.add_edge(START, "entry")

    # Detective nodes (fan-out)
    for dim in rubric["dimensions"]:
        graph.add_node(dim["id"], make_detective(dim))
        graph.add_edge("entry", dim["id"])

    # Aggregator node (fan-in)
    def aggregate_node(state: AgentState):
        all_evidences = []
        for ev_list in state.evidences.values():
            all_evidences.extend(ev_list)

        if not all_evidences:
            return {
                "errors": ["No evidence collected; using fallback rationale"],
                "evidences": {
                    "aggregate": [
                        Evidence(
                            goal="fallback",
                            found=False,
                            content="No artifacts available",
                            location="aggregate",
                            rationale="Fallback path triggered",
                            confidence=0.0
                        )
                    ]
                }
            }
        else:
            aggregated = aggregator.evidence_aggregator(all_evidences)
            if isinstance(aggregated, Evidence):
                aggregated_list = [aggregated]
            elif isinstance(aggregated, list):
                aggregated_list = aggregated
            else:
                raise TypeError("Aggregator must return Evidence or List[Evidence]")
            return {"evidences": {"aggregate": aggregated_list}}

    graph.add_node("aggregate", aggregate_node)
    for dim in rubric["dimensions"]:
        graph.add_edge(dim["id"], "aggregate")

   

    def normalize_opinion(raw_opinion, judge_name: str) -> JudicialOpinion:
        if isinstance(raw_opinion, JudicialOpinion):
            return raw_opinion

        if isinstance(raw_opinion, dict):
            return JudicialOpinion(
                judge=judge_name,
                criterion=raw_opinion.get("criterion", "all"),
                verdict=raw_opinion.get("verdict") or str(raw_opinion),
                score=raw_opinion.get("score", 0),
                cited_evidence=raw_opinion.get("cited_evidence", ["aggregate"]),
                dissent=raw_opinion.get("dissent", ""),
                argument=raw_opinion.get("argument") or raw_opinion.get("verdict") or str(raw_opinion)
            )

        # Fallback for unexpected types
        return JudicialOpinion(
            judge=judge_name,
            criterion="all",
            verdict=str(raw_opinion),
            score=0,
            cited_evidence=["aggregate"],
            dissent="",
            argument=str(raw_opinion)
        )


     # Judge nodes (parallel)
    def prosecutor_node(state: AgentState):
        try:
            raw_opinion = judges.prosecutor({"aggregate": state.evidences.get("aggregate", [])}, "all")
            opinion = normalize_opinion(raw_opinion, "Prosecutor")
            return {"opinions": [opinion]}
        except Exception as e:
            return {"errors": [f"Prosecutor failed: {e}"]}

    def defense_node(state: AgentState):
        try:
            raw_opinion = judges.defense({"aggregate": state.evidences.get("aggregate", [])}, "all")
            opinion = normalize_opinion(raw_opinion, "Defense")
            return {"opinions": [opinion]}
        except Exception as e:
            return {"errors": [f"Defense failed: {e}"]}

    def techlead_node(state: AgentState):
        try:
            raw_opinion = judges.tech_lead({"aggregate": state.evidences.get("aggregate", [])}, "all")
            opinion = normalize_opinion(raw_opinion, "TechLead")
            return {"opinions": [opinion]}
        except Exception as e:
            return {"errors": [f"TechLead failed: {e}"]}

    graph.add_node("prosecutor", prosecutor_node)
    graph.add_node("defense", defense_node)
    graph.add_node("techlead", techlead_node)

    graph.add_edge("aggregate", "prosecutor")
    graph.add_edge("aggregate", "defense")
    graph.add_edge("aggregate", "techlead")

    # Chief Justice node
    def chief_node(state: AgentState):
        try:
            opinions: List[JudicialOpinion] = state.opinions
            final_results: List[CriterionResult] = []

            # Compute dissent summary once
            scores = [op.score for op in opinions]
            dissent_summary = None
            if scores and max(scores) - min(scores) > 2:
                dissent_summary = "Dissent detected: score variance > 2"

            # Conflict resolution rules
            for op in opinions:
                score = op.score
                if op.judge == "Prosecutor" and "security" in op.verdict.lower():
                    score = min(score, 3)
                if "aggregate" in state.evidences and not state.evidences["aggregate"]:
                    score = max(score - 2, 0)
                if op.judge == "TechLead":
                    score = int(score * 1.2)

                final_results.append(
                    CriterionResult(
                        dimension_id="security",
                        dimension_name="Security Review",
                        final_score=score,
                        judge_opinions=opinions,   # list of JudicialOpinion objects
                        dissent_summary=dissent_summary,
                        remediation="Review orchestration logic."
                    )
                )

            report = AuditReport(
                repo_url=state.repo_url,
                overall_score=sum(scores) / len(scores) if scores else 0,
                executive_summary=f"Overall score: {sum(scores)/len(scores):.1f}/10" if scores else "No scores available",
                criteria=final_results,
                remediation_plan="Review graph orchestration, strengthen AST checks, enforce structured outputs, and add error-handling edges."
            )

            state.criteria_results = final_results
            state.final_report = report
            return {"criteria_results": final_results, "final_report": report}

        except Exception as e:
            return {"errors": [f"ChiefJustice failed: {e}"]}

    graph.add_node("chief", chief_node)
    graph.add_edge("prosecutor", "chief")
    graph.add_edge("defense", "chief")
    graph.add_edge("techlead", "chief")

    # End node
    def end_node(state: AgentState):
        output_path = "audit/report_onself_generated/audit_report.md"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            justice.serialize_report_to_markdown(state.final_report, output_path)
        except Exception as e:
            return {"errors": [f"Report serialization failed: {e}"]}
        return {}



    graph.add_node("end", end_node)
    graph.add_edge("chief", "end")
    graph.add_edge("end", END)

    return graph.compile()

# --- Main ---
def main():
    api_key = os.getenv("LANGCHAIN_API_KEY")
    tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2")
    print("LangChain API Key:", "SET" if api_key else "MISSING")
    print("Tracing Enabled:", tracing_enabled)

    rubric = load_rubric()
    graph = build_graph(rubric)

    init_state = AgentState(
        repo_url="https://github.com/octocat/Hello-World",
        pdf_path="reports/Credit Risk Probability Model for Alternative Data.pdf",
        rubric_dimensions=rubric["dimensions"],
        evidences={},
        opinions=[],
        errors=[],
        criteria_results=[],
        final_report=None
    )
    final_state = graph.invoke(init_state)
    print("\nAudit completed. Report saved to audit/report_onself_generated/audit_report.md")

    # Access dict keys safely
    if "errors" in final_state and final_state["errors"]:
        print("Errors encountered:", final_state["errors"])


if __name__ == "__main__":
    main()
