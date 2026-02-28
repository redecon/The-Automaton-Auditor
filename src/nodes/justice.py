from statistics import mean
from typing import List, Optional
from datetime import datetime
from src.state import CriterionResult, AuditReport, JudicialOpinion

MAX_SCORE = 5

def generate_audit_report(repo_url: str, criteria: List[CriterionResult]) -> AuditReport:
    """
    Aggregate all CriterionResults into a single AuditReport.
    """

    def synthesize_judicial_opinions(criteria_list: List[CriterionResult]) -> List[JudicialOpinion]:
        opinions: List[JudicialOpinion] = []
        roles = ["Defense", "Prosecution", "Chief Justice"]

        for c in criteria_list:  # per-dimension opinions
            avg = float(c.final_score)
            for role in roles:
                if role == "Defense":
                    score_val = min(MAX_SCORE, max(0, int(round(avg + 1))))
                elif role == "Prosecution":
                    score_val = min(MAX_SCORE, max(0, int(round(avg - 1))))
                else:
                    score_val = int(round(avg))

                opinions.append(
                    JudicialOpinion(
                        dimension_id=c.dimension_id,   # required field
                        judge=role,
                        score=score_val,               # must be int
                        argument=f"{role} view on {c.dimension_name}: score {avg:.2f}",
                        cited_evidence=[]              # you can fill with detector outputs later
                    )
                )
        return opinions

    def build_remediation_plan(criteria_list: List[CriterionResult]) -> str:
        items = []
        for c in criteria_list:
            if c.remediation:
                items.append(f"{c.dimension_id}: {c.remediation}")
        return "; ".join(items) if items else "No remediation suggested."

    overall = float(mean([float(c.final_score) for c in criteria])) if criteria else 0.0
    opinions = synthesize_judicial_opinions(criteria)
    remediation = build_remediation_plan(criteria)

    return AuditReport(
        repo_url=repo_url,
        generated_by_agent_version="local-dev",
        generated_at=datetime.utcnow().isoformat() + "Z",
        source_repo="local",
        target_repo=repo_url,
        executive_summary="Automated audit run",
        overall_score=overall,
        criteria=criteria,
        judicial_opinions=opinions,
        remediation_plan=remediation
    )

# --- compatibility chief_justice (append to src/nodes/justice.py) ---
from statistics import mean
from typing import List, Optional, Any

# If a chief_justice implementation is already present, this block will not override it.
if "chief_justice" not in globals():

    def _clamp_score(val: Any, max_score: int = 5) -> int:
        try:
            s = int(round(float(val)))
        except Exception:
            s = 0
        if s < 0:
            s = 0
        if s > max_score:
            s = max_score
        return s

    def chief_justice(opinions: List[JudicialOpinion], dimension_id: str, dimension_name: str) -> CriterionResult:
        """
        Minimal chief_justice compatibility wrapper.

        - Computes a mean score from provided JudicialOpinion objects.
        - Applies a simple security rule: if any Prosecution gave score 1, cap at 3.
        - Returns a CriterionResult with judge_opinions preserved.
        """
        # Defensive defaults
        if not opinions:
            return CriterionResult(
                dimension_id=dimension_id,
                dimension_name=dimension_name,
                final_score=1,
                judge_opinions=[],
                dissent_summary="No opinions provided.",
                remediation="No remediation available."
            )

        numeric_scores = []
        for op in opinions:
            try:
                numeric_scores.append(float(getattr(op, "score", 0)))
            except Exception:
                continue

        base_score = mean(numeric_scores) if numeric_scores else 1.0
        rounded = _clamp_score(base_score)

        # Security rule: if any Prosecution gave 1, cap at 3
        try:
            for op in opinions:
                if getattr(op, "judge", "") == "Prosecution" and _clamp_score(getattr(op, "score", 0)) == 1:
                    rounded = min(rounded, 3)
        except Exception:
            pass

        dissent_summary: Optional[str] = None
        try:
            if numeric_scores and (max(numeric_scores) - min(numeric_scores) > 2):
                dissent_summary = "Judges disagreed significantly: " + ", ".join(
                    [f"{getattr(op,'judge','?')}={getattr(op,'score', '?')}" for op in opinions]
                )
        except Exception:
            dissent_summary = None

        remediation = "Review opinions and evidence."

        return CriterionResult(
            dimension_id=dimension_id,
            dimension_name=dimension_name,
            final_score=rounded,
            judge_opinions=opinions,
            dissent_summary=dissent_summary,
            remediation=remediation,
        )
# --- end compatibility block ---
# --- compatibility: serialize_report_to_markdown (append to src/nodes/justice.py) ---
import os
from typing import List, Any

def serialize_report_to_markdown(report: AuditReport, output_path: str):
    """
    Minimal Markdown serializer compatible with callers that expect this symbol.
    Writes the audit report to output_path atomically (via temp file + replace).
    """
    if report is None:
        raise ValueError("serialize_report_to_markdown called with None report")

    lines: List[str] = []
    lines.append(f"# Audit Report for {report.repo_url}")
    lines.append("")
    lines.append(f"**Executive Summary:** {getattr(report, 'executive_summary', '')}")
    lines.append("")
    try:
        overall = float(getattr(report, "overall_score", 0.0))
    except Exception:
        overall = 0.0
    MAX_SCORE = getattr(report, "max_score", 5) if hasattr(report, "max_score") else 5
    pct = (overall / MAX_SCORE) * 100 if MAX_SCORE else 0
    lines.append(f"**Overall Score:** {overall:.2f} / {MAX_SCORE:.2f} — {pct:.0f}%")
    lines.append("")
    lines.append("## Criterion Breakdown")
    lines.append("")

    for c in getattr(report, "criteria", []) or []:
        dim_name = getattr(c, "dimension_name", getattr(c, "dimension_id", "Unknown"))
        final_score = getattr(c, "final_score", "N/A")
        lines.append(f"### {dim_name} (Score: {final_score} / {MAX_SCORE})")
        lines.append("")

        # computed mean for transparency
        try:
            scores = []
            for op in getattr(c, "judge_opinions", []) or []:
                s = getattr(op, "score", None)
                if s is not None:
                    scores.append(float(s))
            if scores:
                float_mean = round(sum(scores) / len(scores), 2)
                lines.append(f"_Computed mean (for transparency): {float_mean:.2f} / {MAX_SCORE:.2f}_")
                lines.append("")
        except Exception:
            pass

        if getattr(c, "judge_opinions", None):
            for op in getattr(c, "judge_opinions", []):
                judge = getattr(op, "judge", "Unknown")
                score = getattr(op, "score", "N/A")
                argument = getattr(op, "argument", "")
                cited = getattr(op, "cited_evidence", None)
                lines.append(f"- **{judge}** ({score}): {argument}")
                if cited:
                    try:
                        lines.append(f"  - Evidence: {', '.join(map(str, cited))}")
                    except Exception:
                        lines.append(f"  - Evidence: {str(cited)}")
        else:
            lines.append("- No judge opinions recorded.")

        if getattr(c, "dissent_summary", None):
            lines.append("")
            lines.append(f"**Dissent:** {c.dissent_summary}")
        if getattr(c, "remediation", None):
            lines.append("")
            lines.append(f"**Remediation:** {c.remediation}")
        else:
            lines.append("")
            lines.append("**Remediation:** No remediation provided.")
        lines.append("")

    lines.append("## Remediation Plan")
    lines.append(getattr(report, "remediation_plan", "No remediation provided."))
    lines.append("")

    # Ensure directory exists and replace any existing file atomically
    out_dir = os.path.dirname(output_path) or "."
    os.makedirs(out_dir, exist_ok=True)
    tmp_path = os.path.join(out_dir, f".tmp_{os.path.basename(output_path)}")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    try:
        if os.path.exists(output_path):
            os.remove(output_path)
    except Exception:
        pass
    os.replace(tmp_path, output_path)

