# src/nodes/judges.py
from src.state import JudicialOpinion
from typing import Dict, Any

def prosecutor(evidence: Dict[str, Any], dimension_id: str) -> JudicialOpinion:
    """
    Return a Prosecutor opinion tied to the rubric dimension_id.
    `evidence` is expected to be a dict like {"aggregate": [...]}.
    """
    has_evidence = bool(evidence and any(v for v in evidence.values()))
    return JudicialOpinion(
        dimension_id=dimension_id,
        judge="Prosecutor",
        criterion="all",
        score=1 if not has_evidence else 3,
        argument="Critical lens: evidence weak" if not has_evidence else "Evidence exists but scrutinized",
        cited_evidence=list(evidence.keys())
    )

def defense(evidence: Dict[str, Any], dimension_id: str) -> JudicialOpinion:
    has_evidence = bool(evidence and any(v for v in evidence.values()))
    return JudicialOpinion(
        dimension_id=dimension_id,
        judge="Defense",
        criterion="all",
        score=5 if has_evidence else 2,
        argument="Optimistic lens: rewarding effort",
        cited_evidence=list(evidence.keys())
    )

def tech_lead(evidence: Dict[str, Any], dimension_id: str) -> JudicialOpinion:
    has_evidence = bool(evidence and any(v for v in evidence.values()))
    return JudicialOpinion(
        dimension_id=dimension_id,
        judge="TechLead",
        criterion="all",
        score=3 if has_evidence else 1,
        argument="Pragmatic lens: maintainability check",
        cited_evidence=list(evidence.keys())
    )
