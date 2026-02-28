from typing import Annotated, List, Dict
import operator
from pydantic import BaseModel, conint, confloat
from pydantic import BaseModel 
from typing import List, Optional
\

class Evidence(BaseModel):
    goal: str
    found: bool
    content: str
    location: str
    rationale: str
    confidence: confloat(ge=0.0, le=1.0)


class JudicialOpinion(BaseModel):
    judge: str
    criterion: Optional[str] = "all"
    verdict: Optional[str] = ""
    score: int = 0
    cited_evidence: List[str] = []
    dissent: Optional[str] = ""
    argument: Optional[str] = ""
      # optional dissent notes

class CriterionResult(BaseModel):
    dimension_id: str
    dimension_name: str
    final_score: int
    judge_opinions: List[JudicialOpinion]   
    dissent_summary: Optional[str] = None
    remediation: str

class AuditReport(BaseModel):
    repo_url: str
    executive_summary: str
    overall_score: float
    criteria: List[CriterionResult]
    remediation_plan: str


class AgentState(BaseModel):
    # Immutable/read-only fields
    repo_url: str
    pdf_path: str
    rubric_dimensions: List[Dict]

    # Reducers for parallel writes
    evidences: Annotated[Dict[str, List[Evidence]], operator.ior]
    opinions: Annotated[List[JudicialOpinion], operator.add]
    errors: Annotated[List[str], operator.add]
    criteria_results: Annotated[List[CriterionResult], operator.add]

    # Single final report
    final_report: AuditReport | None
