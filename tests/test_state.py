import operator
from src.state import AgentState, Evidence, JudicialOpinion

def make_state():
    return AgentState(
        repo_url="https://github.com/octocat/Hello-World",
        pdf_path="reports/test.pdf",
        rubric_dimensions=[],
        evidences={},
        opinions=[],
        errors=[],
        final_report=None
    )

def test_repo_url_mutable():
    state = make_state()
    state.repo_url = "https://github.com/another/repo"
    assert state.repo_url == "https://github.com/another/repo"

def test_evidences_merges_with_operator():
    state = make_state()
    ev1 = Evidence(goal="test1", found=True, content="A", location="node1", rationale="ok", confidence=0.9)
    ev2 = Evidence(goal="test2", found=True, content="B", location="node2", rationale="ok", confidence=0.8)

    state.evidences = operator.ior(state.evidences, {"dim1": [ev1]})
    state.evidences = operator.ior(state.evidences, {"dim2": [ev2]})

    assert "dim1" in state.evidences and "dim2" in state.evidences

def test_opinions_append_with_operator():
    state = make_state()
    op1 = JudicialOpinion(judge="Prosecutor", criterion_id="c1", score=3, argument="arg1", cited_evidence=["e1"])
    op2 = JudicialOpinion(judge="Defense", criterion_id="c2", score=4, argument="arg2", cited_evidence=["e2"])

    state.opinions = operator.add(state.opinions, [op1])
    state.opinions = operator.add(state.opinions, [op2])

    assert len(state.opinions) == 2

def test_errors_append_with_operator():
    state = make_state()
    state.errors = operator.add(state.errors, ["RepoInvestigator failed"])
    state.errors = operator.add(state.errors, ["DocAnalyst failed"])

    assert len(state.errors) == 2
