from src.state import CriterionResult, AuditReport, JudicialOpinion

def chief_justice(repo_url: str, opinions: list[JudicialOpinion], dimension_id: str, dimension_name: str) -> CriterionResult:
    # Simple conflict resolution: prioritize TechLead, cap if Prosecutor finds flaw
    scores = [op.score for op in opinions]
    final_score = max(scores)  # start with highest score
    
    # Rule of Security: if Prosecutor gave 1, cap at 3
    for op in opinions:
        if op.judge == "Prosecutor" and op.score == 1:
            final_score = min(final_score, 3)
    
    dissent_summary = None
    if max(scores) - min(scores) > 2:
        dissent_summary = "Judges disagreed significantly: " + ", ".join([f"{op.judge}={op.score}" for op in opinions])
    
    remediation = "Review src/state.py and src/graph.py for proper parallel orchestration."
    
    return CriterionResult(
        dimension_id=dimension_id,
        dimension_name=dimension_name,
        final_score=final_score,
        judge_opinions=opinions,
        dissent_summary=dissent_summary,
        remediation=remediation,
    )

def generate_audit_report(repo_url: str, criteria: list[CriterionResult]) -> AuditReport:
    overall_score = sum([c.final_score for c in criteria]) / len(criteria)
    executive_summary = f"Audit completed for {repo_url}. Overall score: {overall_score:.2f}."
    remediation_plan = "\n".join([c.remediation for c in criteria])
    
    return AuditReport(
        repo_url=repo_url,
        executive_summary=executive_summary,
        overall_score=overall_score,
        criteria=criteria,
        remediation_plan=remediation_plan,
    )

def serialize_report_to_markdown(report: AuditReport, output_path: str):
    """Convert AuditReport into a structured Markdown file."""
    lines = []
    lines.append(f"# Audit Report for {report.repo_url}\n")
    lines.append(f"**Executive Summary:** {report.executive_summary}\n")
    lines.append(f"**Overall Score:** {report.overall_score:.2f}\n")

    lines.append("\n## Criterion Breakdown\n")
    for c in report.criteria:
        lines.append(f"### {c.dimension_name} (Score: {c.final_score})\n")
        for op in c.judge_opinions:
            lines.append(f"- **{op.judge}** ({op.score}): {op.argument}")
        if c.dissent_summary:
            lines.append(f"\n**Dissent:** {c.dissent_summary}")
        lines.append(f"\n**Remediation:** {c.remediation}\n")

    lines.append("\n## Remediation Plan\n")
    lines.append(report.remediation_plan)

    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
