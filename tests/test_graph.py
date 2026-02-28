import os
from src.graph import build_graph, load_rubric
from src.state import AgentState

def test_graph_runs_end_to_end(tmp_path):
    # Load dummy rubric
    rubric = load_rubric("rubric/rubric.json")
    graph = build_graph(rubric)

    # Initialize state
    state = AgentState(
        repo_url="https://github.com/octocat/Hello-World",
        pdf_path="reports/test.pdf",
        rubric_dimensions=rubric["dimensions"],
        evidences={},
        opinions=[],
        errors=[],
        final_report=None
    )

    # Run graph
    final_state = graph.invoke(state)

    # Assertions
    assert final_state.final_report is not None
    assert isinstance(final_state.final_report, dict) or hasattr(final_state.final_report, "executive_summary")
    assert "criteria_results" in final_state or final_state.errors == []
