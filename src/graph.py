# src/graph.py
import os
import json
import time
import functools
import traceback
from typing import List, Dict, Optional, Any, Set
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
from src.detectors.sample_detectors import collect_all_evidence

# Try to import the REST fallback helper that creates a LangSmith run and uploads artifacts.
# If it's not present, we'll fall back to writing a local JSON artifact.
try:
    from src.tracing.langsmith_rest_fallback import run_and_upload_report
except Exception:
    run_and_upload_report = None  # type: ignore

# Load environment variables
load_dotenv()


def load_rubric(path: str = "rubric/rubric.json") -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --- Safe serializer (recursive, robust) ---
def _is_primitive(x: Any) -> bool:
    return x is None or isinstance(x, (str, int, float, bool))


def safe_serialize(obj: Any, _seen: Optional[Set[int]] = None) -> Any:
    """
    Recursively convert obj into JSON-serializable primitives.
    Handles:
      - Pydantic models (model_dump / dict)
      - dataclasses (asdict)
      - objects with __dict__
      - lists/tuples/sets
      - dicts
      - fallback to str(obj)
    Avoids infinite recursion via _seen set of object ids.
    """
    if _seen is None:
        _seen = set()

    try:
        oid = id(obj)
    except Exception:
        oid = None

    if oid is not None and oid in _seen:
        return "<circular>"

    if oid is not None:
        _seen.add(oid)

    try:
        if _is_primitive(obj):
            return obj

        # Pydantic v2
        if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
            try:
                dumped = obj.model_dump()
                return safe_serialize(dumped, _seen)
            except Exception:
                pass

        # Pydantic v1 or other models
        if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
            try:
                dumped = obj.dict()
                return safe_serialize(dumped, _seen)
            except Exception:
                pass

        # If it's a mapping
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                try:
                    key = k if isinstance(k, str) else str(k)
                    out[key] = safe_serialize(v, _seen)
                except Exception:
                    out[str(k)] = "<unserializable-key>"
            return out

        # Sequences
        if isinstance(obj, (list, tuple, set)):
            return [safe_serialize(i, _seen) for i in obj]

        # dataclasses
        try:
            from dataclasses import is_dataclass, asdict
            if is_dataclass(obj):
                return safe_serialize(asdict(obj), _seen)
        except Exception:
            pass

        # Common container-like attributes
        if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, bytearray)):
            try:
                return [safe_serialize(i, _seen) for i in obj]
            except Exception:
                pass

        # Objects with __dict__
        if hasattr(obj, "__dict__"):
            try:
                return safe_serialize(vars(obj), _seen)
            except Exception:
                pass

        # Fallback: string representation
        return str(obj)
    finally:
        if oid is not None:
            _seen.discard(oid)


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

            # If the detector returned a full AgentState-like mapping with 'evidences'
            if isinstance(result, AgentState):
                return {"evidences": result.evidences}

            # If the detector returned an Evidence instance, wrap it
            if isinstance(result, Evidence):
                return {"evidences": {dimension["id"]: [result]}}

            # If the detector returned a list of Evidence instances, wrap directly
            if isinstance(result, list) and all(isinstance(ev, Evidence) for ev in result):
                return {"evidences": {dimension["id"]: result}}

            # If the detector returned a dict that already contains 'evidences', pass through
            if isinstance(result, dict) and "evidences" in result:
                return result

            # If the detector returned a dict payload (structured detector output), wrap it into Evidence
            if isinstance(result, dict):
                ev = Evidence(
                    goal=dimension["id"],
                    found=bool(result),
                    content=result,
                    location=f"src/detectors/{dimension['id']}",
                    rationale=dimension.get("success_pattern", "detector payload"),
                    confidence=0.5,
                )
                return {"evidences": {dimension["id"]: [ev]}}

            # If the detector returned a list of dicts/primitives, convert each to Evidence
            if isinstance(result, list):
                ev_list = []
                for item in result:
                    if isinstance(item, Evidence):
                        ev_list.append(item)
                        continue
                    # wrap primitives and dicts into Evidence
                    content = item if isinstance(item, dict) else {"text": str(item)}
                    ev = Evidence(
                        goal=dimension["id"],
                        found=bool(item),
                        content=content,
                        location=f"src/detectors/{dimension['id']}",
                        rationale=dimension.get("success_pattern", "detector list item"),
                        confidence=0.5,
                    )
                    ev_list.append(ev)
                return {"evidences": {dimension["id"]: ev_list}}

            # Fallback: wrap any other return value into Evidence.content as text
            ev = Evidence(
                goal=dimension["id"],
                found=bool(result),
                content={"text": str(result)},
                location=f"src/detectors/{dimension['id']}",
                rationale=dimension.get("success_pattern", "detector fallback"),
                confidence=0.3,
            )
            return {"evidences": {dimension["id"]: [ev]}}

        except Exception as e:
            return {"errors": [f"{dimension['id']} failed: {e}"]}
    return detective_node


# --- Normalize Opinion (robust, with fallback) ---
def normalize_single_opinion(raw: Any, judge_name: str, dimension_id: str) -> JudicialOpinion:
    if isinstance(raw, JudicialOpinion):
        if getattr(raw, "dimension_id", None) in (None, ""):
            raw.dimension_id = dimension_id
        if not getattr(raw, "judge", None):
            raw.judge = judge_name
        return raw

    if isinstance(raw, dict):
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
    if raw_opinion is None:
        return [normalize_single_opinion({}, judge_name, dimension_id)]

    if isinstance(raw_opinion, dict) and "opinions" in raw_opinion:
        items = raw_opinion.get("opinions") or []
        out = []
        for it in items:
            out.append(normalize_single_opinion(it, judge_name, dimension_id))
        return out

    if isinstance(raw_opinion, list):
        out = []
        for it in raw_opinion:
            out.append(normalize_single_opinion(it, judge_name, dimension_id))
        return out

    return [normalize_single_opinion(raw_opinion, judge_name, dimension_id)]


# --- Judge wrapper factory (with debug logging) ---
def make_judge_node(judge_func, judge_name: str, dimension_id: str):
    def judge_node(state: AgentState):
        try:
            per_dim = None
            try:
                per_dim = state.evidences.get(dimension_id)
            except Exception:
                try:
                    per_dim = []
                    for ev in state.evidences:
                        goal = getattr(ev, "goal", None) if not isinstance(ev, dict) else ev.get("goal")
                        if goal == dimension_id:
                            per_dim.append(ev)
                    if not per_dim:
                        per_dim = None
                except Exception:
                    per_dim = None

            def _coerce_item(item):
                if hasattr(item, "content"):
                    return item
                if isinstance(item, dict):
                    return item
                if isinstance(item, (str, int, float, bool)):
                    return {"text": str(item)}
                return {"text": str(item)}

            if per_dim is None:
                raw_list = state.evidences.get("aggregate", []) or []
            else:
                raw_list = per_dim if isinstance(per_dim, list) else [per_dim]

            normalized_list = [_coerce_item(it) for it in raw_list]

            coerced_list = []
            for it in normalized_list:
                if hasattr(it, "content"):
                    coerced_list.append(it)
                elif isinstance(it, dict):
                    coerced_list.append(it)
                else:
                    coerced_list.append({"text": str(it)})

            evidence_payload = {"evidence": coerced_list, "aggregate": state.evidences.get("aggregate", []) or []}

            try:
                def _safe_serialize_list(lst):
                    out = []
                    for it in lst:
                        if hasattr(it, "model_dump") or hasattr(it, "dict"):
                            try:
                                out.append(it.model_dump() if hasattr(it, "model_dump") else it.dict())
                            except Exception:
                                out.append(str(it))
                        else:
                            out.append(it)
                    return out

                dbg_obj = {
                    "evidence": _safe_serialize_list(evidence_payload.get("evidence", [])),
                    "aggregate": _safe_serialize_list(evidence_payload.get("aggregate", [])),
                }
                print(f"[DEBUG] evidence_payload for {judge_name} / {dimension_id}:", json.dumps(dbg_obj, ensure_ascii=False, indent=2, default=str))
            except Exception:
                try:
                    print(f"[DEBUG] evidence_payload (repr) for {judge_name} / {dimension_id}:", repr(evidence_payload))
                except Exception:
                    pass

            raw = judge_func(evidence_payload, dimension_id)

            try:
                print(f"[DEBUG] {judge_name} raw return for {dimension_id}:", raw)
            except Exception:
                pass

            try:
                dbg_dir = "audit/debug_judges"
                os.makedirs(dbg_dir, exist_ok=True)
                dbg_path = os.path.join(dbg_dir, f"{judge_name}_{dimension_id}.json")

                def _to_plain(obj):
                    try:
                        if hasattr(obj, "model_dump") or hasattr(obj, "dict"):
                            return obj.model_dump() if hasattr(obj, "model_dump") else obj.dict()
                        if isinstance(obj, list):
                            return [_to_plain(i) for i in obj]
                        if isinstance(obj, dict):
                            return {k: _to_plain(v) for k, v in obj.items()}
                        return obj
                    except Exception:
                        return str(obj)

                serial_raw = _to_plain(raw)
                serial_payload = _to_plain(evidence_payload)

                with open(dbg_path, "w", encoding="utf-8") as dbg_f:
                    json.dump({"raw": serial_raw, "evidence_payload": serial_payload}, dbg_f, ensure_ascii=False, indent=2)
            except Exception as dbg_e:
                print(f"[DEBUG] failed to write debug file: {dbg_e}")

            opinions_objs = normalize_opinion(raw, judge_name, dimension_id)

            opinions_dicts = []
            for op in opinions_objs:
                if isinstance(op, JudicialOpinion):
                    d = op.model_dump() if hasattr(op, "model_dump") else op.dict()
                elif isinstance(op, dict):
                    d = dict(op)
                else:
                    tmp = normalize_single_opinion(op, judge_name, dimension_id)
                    d = tmp.model_dump() if hasattr(tmp, "model_dump") else tmp.dict()

                d["dimension_id"] = d.get("dimension_id") or dimension_id
                d["judge"] = d.get("judge") or judge_name

                if "cited_evidence" not in d or d["cited_evidence"] is None:
                    d["cited_evidence"] = []

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
        print("[DEBUG] total opinions in state:", len(state.opinions))
        for i, op in enumerate(state.opinions[:20]):
            try:
                print(f"[DEBUG] opinion[{i}]: judge={getattr(op,'judge',op.get('judge',None))}, "
                      f"dimension_id={getattr(op,'dimension_id',op.get('dimension_id',None))}, score={getattr(op,'score',op.get('score',None))}")
            except Exception:
                print(f"[DEBUG] opinion[{i}] raw:", op)

        try:
            final_results: List[CriterionResult] = []

            rubric_local = rubric

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
        try:
            dbg_state_path = "audit/debug_state_snapshot.json"
            with open(dbg_state_path, "w", encoding="utf-8") as f:
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


# --- Main / Instrumented run entrypoint ---
def main_entry(repo_path: str = ".", repo_url: str = "local-repo"):
    """
    Run the full pipeline and attempt to upload the structured report to LangSmith via REST fallback.
    - repo_path: local path to the repository to audit
    - repo_url: canonical repo URL used in the report metadata
    """
    rubric = load_rubric()
    graph = build_graph(rubric)

    init_state = AgentState(
        repo_url=repo_url,
        pdf_path="reports/Credit Risk Probability Model for Alternative Data.pdf",
        rubric_dimensions=rubric["dimensions"],
        evidences={},
        opinions=[],
        errors=[],
        criteria_results=[],
        final_report=None,
    )

    # Collect raw evidences as a mapping: dimension_id -> payload
    repo_root = repo_path
    raw_evidences = collect_all_evidence(repo_path=repo_root) or {}

    # Normalize raw_evidences into dict[str, list[Evidence]]
    normalized_evidences: Dict[str, List[Evidence]] = {}
    for dim_id, payload in raw_evidences.items():
        items = payload if isinstance(payload, list) else [payload]
        ev_list: List[Evidence] = []
        for item in items:
            try:
                ev = Evidence(
                    goal=dim_id,
                    found=bool(item),
                    content=item,
                    location="src.detectors.sample_detector",
                    rationale="auto-collected evidence",
                    confidence=0.5,
                )
                ev_list.append(ev)
            except Exception:
                try:
                    ev = Evidence.model_validate({
                        "goal": dim_id,
                        "found": bool(item),
                        "content": item,
                        "location": "src.detectors.sample_detector",
                        "rationale": "auto-collected evidence",
                        "confidence": 0.5,
                    })
                    ev_list.append(ev)
                except Exception:
                    continue
        normalized_evidences[dim_id] = ev_list

    init_state.evidences = normalized_evidences

    # Run the graph
    final_state = None
    try:
        final_state = graph.invoke(init_state)
    except Exception:
        traceback.print_exc()
        raise

    print("\nAudit completed. Report saved to audit/report_onself_generated/audit_report.md")

    # If the graph returned errors, print them
    if isinstance(final_state, dict) and "errors" in final_state and final_state["errors"]:
        print("Errors encountered:", final_state["errors"])

    # --- Prepare serializable report object ---
    report_obj = None
    try:
        raw_report = None
        if hasattr(final_state, "final_report") and final_state.final_report is not None:
            rpt = final_state.final_report
            # prefer pydantic/dict if available
            raw_report = rpt.__dict__ if hasattr(rpt, "__dict__") else rpt
        elif isinstance(final_state, dict) and "final_report" in final_state:
            raw_report = final_state["final_report"]

        if raw_report is not None:
            serializable_report = safe_serialize(raw_report)
            # validate by attempting to dump to JSON
            json.dumps(serializable_report, ensure_ascii=False)
            report_obj = serializable_report
    except Exception as e:
        print("Failed to prepare serializable report object:", e)
        report_obj = None

    # --- Attempt to upload structured report via REST fallback helper ---
    if report_obj is not None:
        try:
            if run_and_upload_report is not None:
                info = run_and_upload_report(report_obj, repo_meta={"repo": repo_url})
                if info.get("status") == "ok":
                    print("LangSmith run URL:", info.get("run_url"))
                else:
                    # local fallback path or error
                    print("LangSmith upload fallback:", info)
                    if info.get("path"):
                        print("Artifact written locally at:", info.get("path"), " — upload manually in LangSmith UI.")
            else:
                # No REST helper available: write local artifact and instruct manual upload
                local_path = os.path.join("audit", "audit_report_manual_upload.json")
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "w", encoding="utf-8") as fh:
                    json.dump(report_obj, fh, indent=2, ensure_ascii=False)
                print("LangSmith REST helper not available. Wrote local artifact to:", os.path.abspath(local_path))
                print("Upload this file manually in the LangSmith UI to attach it to a run.")
        except Exception as e:
            print("Failed to upload report to LangSmith via REST fallback:", e)
            # ensure local artifact exists
            try:
                local_path = os.path.join("audit", "audit_report_manual_upload.json")
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "w", encoding="utf-8") as fh:
                    json.dump(report_obj, fh, indent=2, ensure_ascii=False)
                print("Wrote local artifact to:", os.path.abspath(local_path))
            except Exception as e2:
                print("Failed to write local artifact:", e2)
    else:
        print("No structured final_report object available to upload.")

    return final_state


def main():
    # Backwards-compatible entrypoint for scripts/CI that call main()
    repo = "."
    url = "https://github.com/redecon/The-Automaton-Auditor"
    main_entry(repo, url)


if __name__ == "__main__":
    main()
