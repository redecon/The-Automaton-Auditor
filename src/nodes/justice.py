from statistics import mean
from typing import List, Optional, Any
from src.state import CriterionResult, AuditReport, JudicialOpinion

# report settings
MAX_SCORE = 5


# --- Chief Justice ---
def chief_justice(opinions: List[JudicialOpinion], dimension_id: str, dimension_name: str) -> CriterionResult:
    """
    Resolve conflicts among judicial opinions for a given rubric dimension.
    - Compute per-dimension score as the mean of judge scores.
    - Apply the Rule of Security: if any Prosecutor gave 1, cap at 3.
    - Return final_score as an integer (model expects int).
    """
    if not opinions:
        return CriterionResult(
            dimension_id=dimension_id,
            dimension_name=dimension_name,
            final_score=1,
            judge_opinions=[],
            dissent_summary="No opinions provided.",
            remediation="Ensure judges append opinions to state.opinions."
        )

    # Extract numeric scores defensively
    numeric_scores = []
    for op in opinions:
        try:
            numeric_scores.append(float(op.score))
        except Exception:
            continue

    if not numeric_scores:
        base_score = 1.0
    else:
        base_score = mean(numeric_scores)

    # Apply rounding policy: round to nearest integer
    rounded = int(round(base_score))

    # Rule of Security: if any Prosecutor gave 1, cap at 3
    for op in opinions:
        if getattr(op, "judge", "") == "Prosecutor":
            try:
                if float(op.score) == 1.0:
                    rounded = min(rounded, 3)
            except Exception:
                continue

    # Dissent detection
    dissent_summary: Optional[str] = None
    try:
        if numeric_scores and (max(numeric_scores) - min(numeric_scores) > 2):
            dissent_summary = "Judges disagreed significantly: " + ", ".join(
                [f"{op.judge}={op.score}" for op in opinions]
            )
    except Exception:
        dissent_summary = None

    remediation = "Review src/state.py and src/graph.py for proper parallel orchestration."

    return CriterionResult(
        dimension_id=dimension_id,
        dimension_name=dimension_name,
        final_score=rounded,
        judge_opinions=opinions,
        dissent_summary=dissent_summary,
        remediation=remediation,
    )


# --- Audit Report Generator ---
def generate_audit_report(repo_url: str, criteria: List[CriterionResult]) -> AuditReport:
    """
    Aggregate CriterionResults into an AuditReport.
    - overall_score is the mean of integer final_scores, rounded to 2 decimals for display.
    - Always returns an AuditReport object (never None).
    """
    # Defensive: ensure criteria is a list
    criteria = criteria or []

    if not criteria:
        return AuditReport(
            repo_url=repo_url,
            executive_summary=f"Audit completed for {repo_url}. No criteria evaluated.",
            overall_score=0.0,
            criteria=[],
            remediation_plan="No remediation available."
        )

    # Collect final scores defensively (treat non-numeric as 0)
    scores = []
    for c in criteria:
        try:
            scores.append(float(c.final_score))
        except Exception:
            scores.append(0.0)

    overall_score = round(mean(scores), 2) if scores else 0.0
    executive_summary = f"Audit completed for {repo_url}. Overall score: {overall_score:.2f}."
    remediation_plan = "\n".join([c.remediation for c in criteria if c.remediation])

    return AuditReport(
        repo_url=repo_url,
        executive_summary=executive_summary,
        overall_score=overall_score,
        criteria=criteria,
        remediation_plan=remediation_plan,
    )


# --- Markdown Serializer ---
def serialize_report_to_markdown(report: AuditReport, output_path: str):
    """
    Convert AuditReport into a structured Markdown file.
    Shows scores as 'X/Y' where Y is MAX_SCORE and preserves numeric display.
    """
    # Defensive: ensure report is valid
    if report is None:
        raise ValueError("serialize_report_to_markdown called with None report")

    lines = []
    lines.append(f"# Audit Report for {report.repo_url}\n")
    lines.append(f"**Executive Summary:** {report.executive_summary}\n")
    # show overall as "value / MAX_SCORE"
    lines.append(f"**Overall Score:** {report.overall_score:.2f} / {MAX_SCORE:.2f}\n")

    lines.append("\n## Criterion Breakdown\n")
    for c in report.criteria:
        # show stored final_score and the scale
        lines.append(f"### {c.dimension_name} (Score: {c.final_score} / {MAX_SCORE})\n")

        # compute float mean for transparency (display only)
        float_mean = None
        try:
            scores = []
            for op in c.judge_opinions or []:
                s = getattr(op, "score", None) if not isinstance(op, dict) else op.get("score")
                if s is not None:
                    scores.append(float(s))
            if scores:
                float_mean = round(sum(scores) / len(scores), 2)
        except Exception:
            float_mean = None

        if float_mean is not None:
            lines.append(f"_Computed mean (for transparency): {float_mean:.2f} / {MAX_SCORE:.2f}_\n")

        if c.judge_opinions:
            for op in c.judge_opinions:
                judge = getattr(op, "judge", None) or (op.get("judge") if isinstance(op, dict) else "Unknown")
                score = getattr(op, "score", None) or (op.get("score") if isinstance(op, dict) else "N/A")
                argument = getattr(op, "argument", None) or (op.get("argument") if isinstance(op, dict) else "")
                lines.append(f"- **{judge}** ({score}): {argument}")
        else:
            lines.append("- No judge opinions recorded.")

        if c.dissent_summary:
            lines.append(f"\n**Dissent:** {c.dissent_summary}")
        lines.append(f"\n**Remediation:** {c.remediation}\n")

    lines.append("\n## Remediation Plan\n")
    lines.append(report.remediation_plan or "No remediation provided.")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
