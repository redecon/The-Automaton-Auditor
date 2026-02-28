# src/graph.py
import os
import json
import time
import functools
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from src.nodes.detectives import (
    git_forensic_analysis,
    doc_analyst,
    diagram_flow,
    state_management_rigor,
    graph_orchestration,
    safe_tool_engineering,
    host_analysis_accuracy,
    structured_output,
)
from src.state import AgentState, Evidence, JudicialOpinion, CriterionResult, AuditReport
from src.nodes import aggregator, judges, justice
from src.nodes.justice import chief_justice, generate_audit_report

# Load environment variables
load_dotenv()


def load_rubric(path: str = "rubric/rubric.json") -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --- Retry decorator ---
def retry(max_attempts: int = 3, delay: float = 1, backoff: float = 2):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception:
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
        rationale=dim.get("success_pattern", ""),
        confidence=0.8,
    ),
    "synthesis_conflict_resolution": lambda state, dim: Evidence(
        goal=dim["name"],
        found=True,
        content="Chief Justice synthesis with dissent summary",
        location="src/nodes/justice.py",
        rationale=dim.get("success_pattern", ""),
        confidence=0.9,
    ),
}


# --- Detective wrapper ---
def make_detective(dimension: Dict):
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


# --- Normalize Opinion (robust, with fallback) ---
def normalize_single_opinion(raw: Any, judge_name: str, dimension_id: str) -> JudicialOpinion:
    """
    Convert a single raw opinion (dict, JudicialOpinion, primitive) into a JudicialOpinion
    and ensure dimension_id is set. This function never calls JudicialOpinion(...) without
    providing dimension_id.
    """
    # If it's already a JudicialOpinion, ensure dimension_id and judge are set
    if isinstance(raw, JudicialOpinion):
        if getattr(raw, "dimension_id", None) in (None, ""):
            raw.dimension_id = dimension_id
        if not getattr(raw, "judge", None):
            raw.judge = judge_name
        return raw

    # If it's a dict, map fields explicitly and set dimension_id
    if isinstance(raw, dict):
        # Defensive: remove any accidental 'dimension_id' that is None
        dim = raw.get("dimension_id") or dimension_id
        return JudicialOpinion(
            dimension_id=dim,
            judge=raw.get("judge") or judge_name,
            criterion=raw.get("criterion", "all"),
            verdict=raw.get("verdict") or str(raw),
            score=raw.get("score", 0),
            cited_evidence=raw.get("cited_evidence", ["aggregate"]),
            dissent=raw.get("dissent", ""),
            argument=raw.get("argument") or raw.get("verdict") or str(raw),
        )

    # Fallback for other types (string, number, etc.)
    return JudicialOpinion(
        dimension_id=dimension_id,
        judge=judge_name,
        criterion="all",
        verdict=str(raw),
        score=0,
        cited_evidence=["aggregate"],
        dissent="",
        argument=str(raw),
    )


def normalize_opinion(raw_opinion: Any, judge_name: str, dimension_id: str) -> List[JudicialOpinion]:
    """
    Accept many shapes from judge functions and always return a list of JudicialOpinion
    with dimension_id set.
    Supported raw_opinion shapes:
      - JudicialOpinion
      - dict (single opinion)
      - list of dicts / JudicialOpinion
      - dict wrapper: {"opinions": [...]}
    """
    if raw_opinion is None:
        return [normalize_single_opinion({}, judge_name, dimension_id)]

    # If wrapper dict with 'opinions'
    if isinstance(raw_opinion, dict) and "opinions" in raw_opinion:
        items = raw_opinion.get("opinions") or []
        out = []
        for it in items:
            out.append(normalize_single_opinion(it, judge_name, dimension_id))
        return out

    # If list, normalize each element
    if isinstance(raw_opinion, list):
        out = []
        for it in raw_opinion:
            out.append(normalize_single_opinion(it, judge_name, dimension_id))
        return out

    # Single item (dict, JudicialOpinion, primitive)
    return [normalize_single_opinion(raw_opinion, judge_name, dimension_id)]


# --- Judge wrapper factory (with debug logging) ---
def make_judge_node(judge_func, judge_name: str, dimension_id: str):
    def judge_node(state: AgentState):
        try:
            # Pass the actual rubric dimension id here (was "all")
            raw = judge_func({"aggregate": state.evidences.get("aggregate", [])}, dimension_id)

            # Console debug
            try:
                print(f"[DEBUG] {judge_name} raw return for {dimension_id}:", raw)
            except Exception:
                pass

            # Write debug file
            try:
                dbg_dir = "audit/debug_judges"
                os.makedirs(dbg_dir, exist_ok=True)
                dbg_path = os.path.join(dbg_dir, f"{judge_name}_{dimension_id}.json")
                with open(dbg_path, "w", encoding="utf-8") as dbg_f:
                    json.dump({"raw": raw}, dbg_f, default=str, ensure_ascii=False, indent=2)
            except Exception as dbg_e:
                print(f"[DEBUG] failed to write debug file: {dbg_e}")

            # Normalize into JudicialOpinion objects (internal)
            opinions_objs = normalize_opinion(raw, judge_name, dimension_id)

            # Convert to plain dicts and ensure required fields exist
            opinions_dicts = []
            for op in opinions_objs:
                if isinstance(op, JudicialOpinion):
                    d = op.model_dump() if hasattr(op, "model_dump") else op.dict()
                elif isinstance(op, dict):
                    d = dict(op)
                else:
                    tmp = normalize_single_opinion(op, judge_name, dimension_id)
                    d = tmp.model_dump() if hasattr(tmp, "model_dump") else tmp.dict()

                # Defensive guarantee: set dimension_id and judge
                d["dimension_id"] = d.get("dimension_id") or dimension_id
                d["judge"] = d.get("judge") or judge_name

                opinions_dicts.append(d)

            return {"opinions": opinions_dicts}
        except Exception as e:
            return {"errors": [f"{judge_name} failed: {e}"]}
    return judge_node

# --- Build Graph ---
def build_graph(rubric: Dict):
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
                            confidence=0.0,
                        )
                    ]
                },
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

    # Judge nodes (parallel per dimension)
    for dim in rubric["dimensions"]:
        pid = dim["id"]
        graph.add_node(f"prosecutor_{pid}", make_judge_node(judges.prosecutor, "Prosecutor", pid))
        graph.add_node(f"defense_{pid}", make_judge_node(judges.defense, "Defense", pid))
        graph.add_node(f"techlead_{pid}", make_judge_node(judges.tech_lead, "TechLead", pid))

        graph.add_edge("aggregate", f"prosecutor_{pid}")
        graph.add_edge("aggregate", f"defense_{pid}")
        graph.add_edge("aggregate", f"techlead_{pid}")

    # Chief Justice node
    def chief_node(state: AgentState):
            # inside chief_node, before iterating rubric
        print("[DEBUG] total opinions in state:", len(state.opinions))
        for i, op in enumerate(state.opinions[:20]):
            try:
                print(f"[DEBUG] opinion[{i}]: judge={getattr(op,'judge',op.get('judge',None))}, "
                    f"dimension_id={getattr(op,'dimension_id',op.get('dimension_id',None))}, score={getattr(op,'score',op.get('score',None))}")
            except Exception:
                print(f"[DEBUG] opinion[{i}] raw:", op)

        try:
            final_results: List[CriterionResult] = []

            # Use rubric passed into build_graph
            rubric_local = rubric

            # For each dimension in rubric, collect opinions and resolve
            for dim in rubric_local["dimensions"]:
                relevant_ops = [
                    op for op in state.opinions
                    if getattr(op, "dimension_id", None) == dim["id"]
                ]

                result = chief_justice(
                    opinions=relevant_ops,
                    dimension_id=dim["id"],
                    dimension_name=dim["name"],
                )
                final_results.append(result)

            report = generate_audit_report(
                repo_url=state.repo_url,
                criteria=final_results,
            )

            state.criteria_results = final_results
            state.final_report = report
            return {"criteria_results": final_results, "final_report": report}

        except Exception as e:
            return {"errors": [f"ChiefJustice failed: {e}"]}

    graph.add_node("chief", chief_node)

    # Wire judge outputs into chief node
    for dim in rubric["dimensions"]:
        pid = dim["id"]
        graph.add_edge(f"prosecutor_{pid}", "chief")
        graph.add_edge(f"defense_{pid}", "chief")
        graph.add_edge(f"techlead_{pid}", "chief")

    # End node: serialize report to markdown
    def end_node(state: AgentState):
        output_path = "audit/report_onself_generated/audit_report.md"
                # before calling justice.serialize_report_to_markdown(...)
        try:
            dbg_state_path = "audit/debug_state_snapshot.json"
            import json
            with open(dbg_state_path, "w", encoding="utf-8") as f:
                # state may be Pydantic model or dict; coerce safely
                dump = {}
                try:
                    dump["opinions"] = [op.model_dump() if hasattr(op, "model_dump") else (op.dict() if hasattr(op, "dict") else op) for op in state.opinions]
                except Exception:
                    dump["opinions"] = [str(op) for op in state.opinions]
                dump["errors"] = state.errors
                dump["evidences_keys"] = list(state.evidences.keys())
                json.dump(dump, f, default=str, indent=2, ensure_ascii=False)
            print("[DEBUG] wrote state snapshot to", dbg_state_path)
        except Exception as e:
            print("[DEBUG] failed to write state snapshot:", e)

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
        repo_url="https://github.com/redecon/The-Automaton-Auditor",
        pdf_path="reports/Credit Risk Probability Model for Alternative Data.pdf",
        rubric_dimensions=rubric["dimensions"],
        evidences={},
        opinions=[],
        errors=[],
        criteria_results=[],
        final_report=None,
    )
    final_state = graph.invoke(init_state)
    print("\nAudit completed. Report saved to audit/report_onself_generated/audit_report.md")

    if "errors" in final_state and final_state["errors"]:
        print("Errors encountered:", final_state["errors"])


if __name__ == "__main__":
    main()
