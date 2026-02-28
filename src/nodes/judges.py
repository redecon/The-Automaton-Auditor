# src/nodes/judges.py
from typing import Dict, Any, List
from src.state import JudicialOpinion

# -------------------------
# Utilities
# -------------------------
def _has_items(x: Any) -> bool:
    """Helper: treat non-empty lists/dicts/strings as evidence present."""
    if x is None:
        return False
    if isinstance(x, (list, tuple, set)):
        return len(x) > 0
    if isinstance(x, dict):
        return any(_has_items(v) for v in x.values())
    if isinstance(x, str):
        return x.strip() != ""
    return True

def _evidence_keys_present(evidence: Dict[str, Any], keys: List[str]) -> List[str]:
    """Return which of the requested keys are present and non-empty."""
    return [k for k in keys if k in evidence and _has_items(evidence[k])]

def _unwrap_evidence_wrapper(evidence_wrapper: Any) -> Dict[str, Any]:
    if evidence_wrapper is None:
        return {}

    # If it's already a dict with expected keys, return it
    if isinstance(evidence_wrapper, dict) and any(
        k in evidence_wrapper for k in ("commits", "schema", "diagrams", "docs", "tests", "hosts", "examples", "orchestration", "text")
    ):
        return evidence_wrapper

    # Extract list if wrapper has 'evidence' or if it's a list
    ev_list = None
    if isinstance(evidence_wrapper, dict) and "evidence" in evidence_wrapper:
        ev_list = evidence_wrapper.get("evidence") or []
    elif isinstance(evidence_wrapper, list):
        ev_list = evidence_wrapper
    else:
        # Evidence-like object with .content
        if hasattr(evidence_wrapper, "content"):
            try:
                content = getattr(evidence_wrapper, "content")
                if isinstance(content, dict):
                    return content
                if isinstance(content, (str, int, float, bool)):
                    return {"text": str(content)}
                return {"text": str(content)}
            except Exception:
                return {}
        if isinstance(evidence_wrapper, (str, int, float, bool)):
            return {"text": str(evidence_wrapper)}
        return {}

    if not ev_list:
        return {}

    first = ev_list[0]

    if hasattr(first, "content"):
        try:
            content = getattr(first, "content")
            if isinstance(content, dict):
                return content
            if isinstance(content, (str, int, float, bool)):
                return {"text": str(content)}
            return {"text": str(content)}
        except Exception:
            return {}

    if isinstance(first, dict):
        return first

    if isinstance(first, (str, int, float, bool)):
        return {"text": str(first)}

    return {}


# -------------------------
# Prosecutor: skeptical, focuses on provenance, safety, and missing artifacts
# -------------------------
def prosecutor(evidence: Dict[str, Any], dimension_id: str) -> JudicialOpinion:
    # Defensive coercion: ensure the incoming 'evidence' is a dict wrapper the rest of the function expects.
    # This handles cases where the graph accidentally passed a string or primitive.
    if not isinstance(evidence, dict):
        # wrap primitives and lists into the expected shape
        evidence = {"evidence": evidence if isinstance(evidence, list) else [evidence]}

    # Now normalize into a payload dict safe to call .get(...) on
    payload = _unwrap_evidence_wrapper(evidence)


    # Lightweight signals
    commits = bool(payload.get("commits"))
    schema = bool(payload.get("schema") or payload.get("schema_files"))
    diagrams = bool(payload.get("diagrams"))
    hosts = bool(payload.get("hosts"))
    tests = bool(payload.get("tests") or payload.get("orchestration_tests"))

    cited = _evidence_keys_present(payload, ["commits", "schema", "diagrams", "hosts", "tests", "docs", "examples"])

    # Dimension-specific skepticism
    if dimension_id == "git_forensic_analysis":
        score = 1 if not commits else 3
        argument = "Missing commit history or provenance" if not commits else "Commit provenance present but needs deeper checks"
    elif dimension_id == "safe_tool_engineering":
        score = 1 if not tests else 3
        argument = "Tool safety tests absent" if not tests else "Tool tests exist but require coverage review"
    elif dimension_id == "host_analysis_accuracy":
        score = 1 if not hosts else 3
        argument = "Host fingerprints missing" if not hosts else "Host evidence present but needs validation"
    elif dimension_id == "structured_output":
        score = 1 if not schema else 3
        argument = "No output schema found" if not schema else "Schema exists but should be validated against examples"
    else:
        has_any = bool(payload and any(_has_items(v) for v in payload.values()))
        score = 1 if not has_any else 3
        argument = "Evidence weak or missing" if not has_any else "Evidence exists but scrutinized"

    return JudicialOpinion(
        dimension_id=dimension_id,
        judge="Prosecutor",
        criterion="all",
        score=score,
        argument=argument,
        cited_evidence=cited
    )

# -------------------------
# Defense: optimistic, rewards documentation, examples, and presence of artifacts
# -------------------------
def defense(evidence: Dict[str, Any], dimension_id: str) -> JudicialOpinion:
    # Defensive coercion: ensure the incoming 'evidence' is a dict wrapper the rest of the function expects.
    # This handles cases where the graph accidentally passed a string or primitive.
    if not isinstance(evidence, dict):
        # wrap primitives and lists into the expected shape
        evidence = {"evidence": evidence if isinstance(evidence, list) else [evidence]}

    # Now normalize into a payload dict safe to call .get(...) on
    payload = _unwrap_evidence_wrapper(evidence)

    docs = bool(payload.get("docs"))
    examples = bool(payload.get("examples"))
    schema = bool(payload.get("schema") or payload.get("schema_files"))
    diagrams = bool(payload.get("diagrams"))

    cited = _evidence_keys_present(payload, ["docs", "examples", "schema", "diagrams", "commits"])

    if dimension_id in ("structured_output", "doc_analyst"):
        score = 5 if (docs or examples or schema) else 3
        argument = "Good documentation or examples" if (docs or examples or schema) else "Documentation or examples missing"
    elif dimension_id == "diagram_flow":
        score = 5 if diagrams else 3
        argument = "Clear diagrams provided" if diagrams else "Diagrams missing or unclear"
    else:
        has_any = bool(payload and any(_has_items(v) for v in payload.values()))
        score = 4 if has_any else 2
        argument = "Optimistic lens: rewarding effort" if has_any else "Limited evidence"

    return JudicialOpinion(
        dimension_id=dimension_id,
        judge="Defense",
        criterion="all",
        score=score,
        argument=argument,
        cited_evidence=cited
    )

# -------------------------
# TechLead: pragmatic, focuses on maintainability, orchestration, tests, and infra
# -------------------------
def tech_lead(evidence: Dict[str, Any], dimension_id: str) -> JudicialOpinion:
    # Defensive coercion: ensure the incoming 'evidence' is a dict wrapper the rest of the function expects.
    # This handles cases where the graph accidentally passed a string or primitive.
    if not isinstance(evidence, dict):
        # wrap primitives and lists into the expected shape
        evidence = {"evidence": evidence if isinstance(evidence, list) else [evidence]}

    # Now normalize into a payload dict safe to call .get(...) on
    payload = _unwrap_evidence_wrapper(evidence)


    orchestration = bool(payload.get("orchestration") or payload.get("workflow_files"))
    tests = bool(payload.get("tests") or payload.get("orchestration_tests"))
    commits = bool(payload.get("commits"))
    schema = bool(payload.get("schema") or payload.get("schema_files"))

    cited = _evidence_keys_present(payload, ["orchestration", "tests", "commits", "schema", "docs"])

    if dimension_id == "graph_orchestration":
        score = 2 if not orchestration else 4
        argument = "Orchestration artifacts missing; check node contracts" if not orchestration else "Orchestration present but verify parallel safety"
    elif dimension_id == "state_management_rigor":
        score = 2 if not tests else 4
        argument = "State tests and snapshots missing" if not tests else "State management tests present"
    elif dimension_id == "structured_output":
        score = 2 if not schema else 4
        argument = "No schema for outputs; risk of brittle consumers" if not schema else "Schema present; check versioning and validation"
    else:
        has_any = bool(payload and any(_has_items(v) for v in payload.values()))
        score = 3 if has_any else 1
        argument = "Pragmatic lens: maintainability check" if has_any else "Technical artifacts missing"

    return JudicialOpinion(
        dimension_id=dimension_id,
        judge="TechLead",
        criterion="all",
        score=score,
        argument=argument,
        cited_evidence=cited
    )
