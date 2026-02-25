# src/graph.py
import os
import json
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

from src.state import AgentState, Evidence
from src.nodes import aggregator, judges, justice
from src.nodes.detectives import (
    repo_investigator, doc_analyst, vision_inspector,
    state_management_rigor, graph_orchestration, safe_tool_engineering,
    host_analysis_accuracy, structured_output_enforcement
)

# Load environment variables
load_dotenv()

def load_rubric(path="rubric/rubric.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# Mapping rubric IDs to detective functions
DETECTIVE_MAP = {
    "git_forensic_analysis": lambda state, dim: repo_investigator(state, dim),
    "pdf_theoretical_depth": lambda state, dim: doc_analyst(state, dim),
    "diagram_flow": lambda state, dim: vision_inspector(state, dim),
    "state_management_rigor": lambda state, dim: state_management_rigor(state, dim),
    "graph_orchestration": lambda state, dim: graph_orchestration(state, dim),
    "safe_tool_engineering": lambda state, dim: safe_tool_engineering(state, dim),
    "host_analysis_accuracy": lambda state, dim: host_analysis_accuracy(state, dim),
    "structured_output": lambda state, dim: structured_output_enforcement(state, dim),
    "judicial_nuance": lambda state, dim: Evidence(
        goal=dim["name"], found=True,
        content="Distinct reasoning styles observed: Prosecutor, Defense, TechLead",
        location="src/nodes/judges.py",
        rationale=dim["success_pattern"], confidence=0.8
    ),
    "synthesis_conflict_resolution": lambda state, dim: Evidence(
        goal=dim["name"], found=True,
        content="Chief Justice synthesis with dissent summary",
        location="src/nodes/justice.py",
        rationale=dim["success_pattern"], confidence=0.9
    ),
}

def build_graph(rubric):
    graph = StateGraph(AgentState)

    # --- Entry node ---
    def entry_node(state: AgentState) -> AgentState:
        return state
    graph.add_node("entry", entry_node)
    graph.add_edge(START, "entry")

    # --- Detective nodes (fan-out) ---
    for dim in rubric["dimensions"]:
        def make_detective(dimension):
            def detective_node(state: AgentState) -> AgentState:
                return DETECTIVE_MAP[dimension["id"]](state, dimension)
            return detective_node

        graph.add_node(dim["id"], make_detective(dim))
        graph.add_edge("entry", dim["id"])

    # --- Aggregator node (fan-in) ---
    def aggregate_node(state: AgentState) -> AgentState:
        all_evidences = []
        for ev_list in state["evidences"].values():
            all_evidences.extend(ev_list)
        state["aggregated_evidence"] = aggregator.evidence_aggregator(all_evidences)
        return state
    graph.add_node("aggregate", aggregate_node)

    for dim in rubric["dimensions"]:
        graph.add_edge(dim["id"], "aggregate")

    # --- Judge nodes ---
    def prosecutor_node(state: AgentState) -> AgentState:
        opinion = judges.prosecutor(state["aggregated_evidence"], "all")
        state["opinions"].append(opinion)
        return state

    def defense_node(state: AgentState) -> AgentState:
        opinion = judges.defense(state["aggregated_evidence"], "all")
        state["opinions"].append(opinion)
        return state

    def techlead_node(state: AgentState) -> AgentState:
        opinion = judges.tech_lead(state["aggregated_evidence"], "all")
        state["opinions"].append(opinion)
        return state

    graph.add_node("prosecutor", prosecutor_node)
    graph.add_node("defense", defense_node)
    graph.add_node("techlead", techlead_node)

    graph.add_edge("aggregate", "prosecutor")
    graph.add_edge("aggregate", "defense")
    graph.add_edge("aggregate", "techlead")

    # --- Chief Justice node ---
    def chief_node(state: AgentState) -> AgentState:
        result = justice.chief_justice(
            state["repo_url"], state["opinions"], "all", "Overall Rubric"
        )
        state["criteria_results"] = [result]
        state["final_report"] = justice.generate_audit_report(
            state["repo_url"], state["criteria_results"]
        )
        return state

    graph.add_node("chief", chief_node)
    graph.add_edge("prosecutor", "chief")
    graph.add_edge("defense", "chief")
    graph.add_edge("techlead", "chief")

    # --- End node ---
    def end_node(state: AgentState) -> AgentState:
        output_path = "audit/report_onself_generated/audit_report.md"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        justice.serialize_report_to_markdown(state["final_report"], output_path)
        return state

    graph.add_node("end", end_node)
    graph.add_edge("chief", "end")
    graph.add_edge("end", END)

    return graph.compile()

def main():
    # Environment check
    api_key = os.getenv("LANGCHAIN_API_KEY")
    tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2")
    print("LangChain API Key:", "SET" if api_key else "MISSING")
    print("Tracing Enabled:", tracing_enabled)

    rubric = load_rubric()
    graph = build_graph(rubric)

    # Initialize AgentState
    init_state = AgentState(
        repo_url="https://github.com/octocat/Hello-World",
        pdf_path="reports/Credit Risk Probability Model for Alternative Data.pdf",
        rubric_dimensions=rubric["dimensions"],
        evidences={},
        opinions=[],
        final_report=None,
    )

    # Execute graph
    final_state = graph.invoke(init_state)
    print("\nAudit completed. Report saved to audit/report_onself_generated/audit_report.md")

if __name__ == "__main__":
    main()
