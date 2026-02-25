from typing import Annotated, List, Dict
import operator
from pydantic import BaseModel, conint, confloat

class Evidence(BaseModel):
    goal: str
    found: bool
    content: str
    location: str
    rationale: str
    confidence: confloat(ge=0.0, le=1.0)  # confidence between 0 and 1

class JudicialOpinion(BaseModel):
    judge: str
    criterion_id: str
    score: conint(ge=1, le=5)  # score between 1 and 5
    argument: str
    cited_evidence: List[str]

class CriterionResult(BaseModel):
    dimension_id: str
    dimension_name: str
    final_score: conint(ge=1, le=5)
    judge_opinions: List[JudicialOpinion]
    dissent_summary: str | None
    remediation: str

class AuditReport(BaseModel):
    repo_url: str
    executive_summary: str
    overall_score: confloat(ge=0.0, le=5.0)
    criteria: List[CriterionResult]
    remediation_plan: str

class AgentState(BaseModel):
    # Immutable fields (set once, not rewritten)
    repo_url: str
    pdf_path: str
    rubric_dimensions: List[Dict]

    # Reducers for parallel writes
    evidences: Annotated[
        Dict[str, List[Evidence]],
        operator.ior   # merge dicts
    ]
    opinions: Annotated[
        List[JudicialOpinion],
        operator.add   # append lists
    ]

    # Single final report
    final_report: AuditReport | None
