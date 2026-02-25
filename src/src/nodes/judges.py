from src.state import JudicialOpinion

def prosecutor(evidence: dict, criterion_id: str) -> JudicialOpinion:
    return JudicialOpinion(
        judge="Prosecutor",
        criterion_id=criterion_id,
        score=1 if not evidence else 3,
        argument="Critical lens: evidence weak" if not evidence else "Evidence exists but scrutinized",
        cited_evidence=list(evidence.keys())
    )

def defense(evidence: dict, criterion_id: str) -> JudicialOpinion:
    return JudicialOpinion(
        judge="Defense",
        criterion_id=criterion_id,
        score=5 if evidence else 2,
        argument="Optimistic lens: rewarding effort",
        cited_evidence=list(evidence.keys())
    )

def tech_lead(evidence: dict, criterion_id: str) -> JudicialOpinion:
    return JudicialOpinion(
        judge="TechLead",
        criterion_id=criterion_id,
        score=3 if evidence else 1,
        argument="Pragmatic lens: maintainability check",
        cited_evidence=list(evidence.keys())
    )
