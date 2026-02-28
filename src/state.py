from typing import Annotated, List, Dict, Optional
import operator
from pydantic import BaseModel, conint, confloat


# --- Evidence Model ---
from typing import Union, Dict, Any, Optional
from pydantic import BaseModel

class Evidence(BaseModel):
    goal: str
    found: bool
    content: Optional[Union[str, Dict[str, Any]]] = None
    location: Optional[str] = None
    rationale: Optional[str] = None
    confidence: Optional[float] = None


# --- Judicial Opinion ---
class JudicialOpinion(BaseModel):
    dimension_id: str                  # REQUIRED: ties opinion to rubric dimension
    judge: str                         # e.g., "Prosecutor", "Defense", "TechLead"
    criterion: Optional[str] = "all"   # optional: which criterion within dimension
    verdict: Optional[str] = ""        # textual verdict
    score: conint(ge=0, le=10) = 0     # numeric score 0–10
    cited_evidence: List[str] = []     # references to Evidence IDs
    dissent: Optional[str] = ""        # optional dissent notes
    argument: Optional[str] = ""       # reasoning narrative


# --- Criterion Result ---
class CriterionResult(BaseModel):
    dimension_id: str
    dimension_name: str
    final_score: int
    judge_opinions: List[JudicialOpinion]
    dissent_summary: Optional[str] = None
    remediation: str


# --- Audit Report ---
class AuditReport(BaseModel):
    max_score: float = 5.0
    repo_url: str
    executive_summary: str
    overall_score: float
    criteria: List[CriterionResult]
    remediation_plan: str


# --- Agent State ---
class AgentState(BaseModel):
    # Immutable/read-only fields
    repo_url: str
    pdf_path: Optional[str] = None
    rubric_dimensions: List[Dict]

    # Reducers for parallel writes
    evidences: Annotated[Dict[str, List[Evidence]], operator.ior]
    opinions: Annotated[List[JudicialOpinion], operator.add]
    errors: Annotated[List[str], operator.add]
    criteria_results: Annotated[List[CriterionResult], operator.add]

    # Single final report
    final_report: Optional[AuditReport] = None
