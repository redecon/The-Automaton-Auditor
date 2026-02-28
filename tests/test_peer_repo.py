"""
Peer audit runner that:
 - uses detectors that return stable keys/lists,
 - synthesizes per-dimension opinions with evidence,
 - resolves final scores via chief_justice,
 - clamps scores to integers,
 - serializes Markdown showing evidence and treating 0 as valid,
 - replaces any existing audit report file with the newly generated one.
"""

import os
import sys
from statistics import mean
from typing import List, Optional, Any
from datetime import datetime
from pathlib import Path

from src.state import CriterionResult, AuditReport, JudicialOpinion
from src.detectors import sample_detectors

MAX_SCORE = 5

REMEDIATION_BY_DIM = {
    "git_forensic_analysis": "Require signed commits; add CI check 'git log --show-signature'; include commit SHAs in audit.",
    "state_management_rigor": "Introduce immutable state snapshots and unit tests for reducers.",
    "graph_orchestration": "Document node contracts and ensure parallel execution is tested.",
    "safe_tool_engineering": "Add tool sandboxing and input validation for external tools.",
    "structured_output": "Add JSON Schema and validate detector outputs in CI.",
    "doc_analyst": "Add usage examples and API docs; cite exact file paths in detectors.",
    "host_analysis_accuracy": "Add host fingerprinting tests and ground-truth checks.",
    "diagram_flow": "Annotate diagrams with data flow and failure modes; include diagram file references.",
    "judicial_nuance": "Encourage judges to include short verdicts and dissent rationale.",
    "synthesis_conflict_resolution": "Add explicit tie-break rules and weighting documentation.",
}


# Utility: clamp score to integer in [0, MAX_SCORE]
def clamp_score(val: Any) -> int:
    try:
        s = int(round(float(val)))
    except Exception:
        s = 0
    if s < 0:
        s = 0
    if s > MAX_SCORE:
        s = MAX_SCORE
    return s


# Chief justice (conflict resolution)
def chief_justice(opinions: List[JudicialOpinion], dimension_id: str, dimension_name: str) -> CriterionResult:
    if not opinions:
        return CriterionResult(
            dimension_id=dimension_id,
            dimension_name=dimension_name,
            final_score=1,
            judge_opinions=[],
            dissent_summary="No opinions provided.",
            remediation=REMEDIATION_BY_DIM.get(dimension_id, "Ensure judges append opinions to state.opinions.")
        )

    numeric_scores = []
    for op in opinions:
        try:
            numeric_scores.append(float(op.score))
        except Exception:
            continue

    base_score = mean(numeric_scores) if numeric_scores else 1.0
    rounded = clamp_score(base_score)

    # Rule of Security: if any Prosecution gave 1, cap at 3
    for op in opinions:
        try:
            if getattr(op, "judge", "") == "Prosecution" and clamp_score(op.score) == 1:
                rounded = min(rounded, 3)
        except Exception:
            continue

    dissent_summary: Optional[str] = None
    try:
        if numeric_scores and (max(numeric_scores) - min(numeric_scores) > 2):
            dissent_summary = "Judges disagreed significantly: " + ", ".join(
                [f"{op.judge}={op.score}" for op in opinions]
            )
    except Exception:
        dissent_summary = None

    remediation = REMEDIATION_BY_DIM.get(dimension_id, "Review code and orchestration for issues.")

    return CriterionResult(
        dimension_id=dimension_id,
        dimension_name=dimension_name,
        final_score=rounded,
        judge_opinions=opinions,
        dissent_summary=dissent_summary,
        remediation=remediation,
    )


# Helper: synthesize opinions for a single criterion
def synthesize_judicial_opinions_single(
    dimension_id: str,
    dimension_name: str,
    base_score: Any,
    evidence: Optional[List[str]] = None
) -> List[JudicialOpinion]:
    if evidence is None:
        evidence = []

    roles = ["Defense", "Prosecution", "Chief Justice"]
    opinions: List[JudicialOpinion] = []
    base = clamp_score(base_score)

    for role in roles:
        if role == "Defense":
            score_val = clamp_score(base + 1)
        elif role == "Prosecution":
            score_val = clamp_score(base - 1)
        else:
            score_val = clamp_score(base)

        # Short argument only; evidence goes into cited_evidence
        argument = f"{role} verdict on {dimension_name}: base score {base}."

        opinions.append(
            JudicialOpinion(
                dimension_id=dimension_id,
                judge=role,
                score=score_val,
                argument=argument,
                cited_evidence=evidence[:5]
            )
        )

    return opinions


# Build criteria from detectors, using chief_justice to compute canonical CriterionResult
def build_criteria_from_detectors(repo_path: str) -> List[CriterionResult]:
    criteria: List[CriterionResult] = []

    # Git forensic analysis
    git_ev = sample_detectors.detect_git_evidence(repo_path) or {}
    git_count = int(git_ev.get("commit_count", 0) or 0)
    git_evidence = []
    git_evidence += git_ev.get("commit_shas", []) if isinstance(git_ev.get("commit_shas", []), list) else []
    git_evidence += git_ev.get("recent_commits", []) if isinstance(git_ev.get("recent_commits", []), list) else []
    git_evidence = [str(x) for x in git_evidence][:5]
    git_base = 4 if git_count > 0 else 1
    git_opinions = synthesize_judicial_opinions_single("git_forensic_analysis", "Git Forensic Analysis", git_base, git_evidence)
    git_criterion = chief_justice(git_opinions, "git_forensic_analysis", "Git Forensic Analysis")
    git_rem = REMEDIATION_BY_DIM["git_forensic_analysis"]
    if git_evidence:
        git_rem = f"{git_rem} Evidence: {', '.join(git_evidence[:3])}"
    git_criterion.remediation = git_rem
    criteria.append(git_criterion)

    # Structured output (schema)
    schema_ev = sample_detectors.detect_schema_files(repo_path) or {}
    schema_files = schema_ev.get("schema_files", []) if isinstance(schema_ev.get("schema_files", []), list) else []
    schema_evidence = [str(p) for p in schema_files][:5]
    schema_base = 3 if schema_files else 1
    schema_opinions = synthesize_judicial_opinions_single("structured_output", "Structured Output Enforcement", schema_base, schema_evidence)
    schema_criterion = chief_justice(schema_opinions, "structured_output", "Structured Output Enforcement")
    schema_rem = REMEDIATION_BY_DIM["structured_output"]
    if schema_evidence:
        schema_rem = f"{schema_rem} Evidence: {', '.join(schema_evidence[:3])}"
    schema_criterion.remediation = schema_rem
    criteria.append(schema_criterion)

    # Diagram evidence
    diag_ev = sample_detectors.detect_diagrams(repo_path) or {}
    diagram_count = int(diag_ev.get("diagram_count", 0) or 0)
    diagram_paths = diag_ev.get("diagram_paths", []) if isinstance(diag_ev.get("diagram_paths", []), list) else []
    diag_evidence = [str(p) for p in diagram_paths][:5]
    diag_base = 3 if diagram_count > 0 else 1
    diag_opinions = synthesize_judicial_opinions_single("diagram_flow", "Diagram & Flow Evidence", diag_base, diag_evidence)
    diag_criterion = chief_justice(diag_opinions, "diagram_flow", "Diagram & Flow Evidence")
    diag_rem = REMEDIATION_BY_DIM["diagram_flow"]
    if diag_evidence:
        diag_rem = f"{diag_rem} Evidence: {', '.join(diag_evidence[:3])}"
    diag_criterion.remediation = diag_rem
    criteria.append(diag_criterion)

    # Orchestration
    orch_ev = sample_detectors.detect_orchestration(repo_path) or {}
    orch_info = orch_ev.get("orchestration", {}) if isinstance(orch_ev.get("orchestration", {}), dict) else {}
    uses_async = bool(orch_info.get("uses_async", False))
    orch_graphs = orch_info.get("graph_files", []) if isinstance(orch_info.get("graph_files", []), list) else []
    orch_evidence = [str(p) for p in orch_graphs][:5]
    orch_base = 3 if uses_async or orch_graphs else 1
    orch_opinions = synthesize_judicial_opinions_single("graph_orchestration", "Graph Orchestration", orch_base, orch_evidence)
    orch_criterion = chief_justice(orch_opinions, "graph_orchestration", "Graph Orchestration")
    orch_rem = REMEDIATION_BY_DIM["graph_orchestration"]
    if uses_async or orch_evidence:
        extra = f"uses_async={uses_async}"
        if orch_evidence:
            extra += f"; graphs={', '.join(orch_evidence[:3])}"
        orch_rem = f"{orch_rem} Evidence: {extra}"
    orch_criterion.remediation = orch_rem
    criteria.append(orch_criterion)

    # Documentation & examples
    docs_ev = sample_detectors.detect_docs_and_examples(repo_path) or {}
    docs_list = docs_ev.get("docs", []) if isinstance(docs_ev.get("docs", []), list) else []
    docs_list = [p for p in docs_list if ".venv" not in p and ".pytest_cache" not in p and "site-packages" not in p]
    docs_evidence = [str(p) for p in docs_list][:5]
    docs_base = 4 if docs_list else 1
    docs_opinions = synthesize_judicial_opinions_single("doc_analyst", "Documentation & Examples", docs_base, docs_evidence)
    docs_criterion = chief_justice(docs_opinions, "doc_analyst", "Documentation & Examples")
    docs_rem = REMEDIATION_BY_DIM["doc_analyst"]
    if docs_evidence:
        docs_rem = f"{docs_rem} Evidence: {', '.join(docs_evidence[:3])}"
    docs_criterion.remediation = docs_rem
    criteria.append(docs_criterion)

    # Host analysis
    host_ev = sample_detectors.detect_hosts(repo_path) or {}
    hosts = host_ev.get("hosts", []) if isinstance(host_ev.get("hosts", []), list) else []
    host_evidence = [str(h) for h in hosts][:5]
    host_base = 2 if hosts else 1
    host_opinions = synthesize_judicial_opinions_single("host_analysis_accuracy", "Host Analysis Accuracy", host_base, host_evidence)
    host_criterion = chief_justice(host_opinions, "host_analysis_accuracy", "Host Analysis Accuracy")
    host_rem = REMEDIATION_BY_DIM["host_analysis_accuracy"]
    if host_evidence:
        host_rem = f"{host_rem} Evidence: {', '.join(host_evidence[:3])}"
    host_criterion.remediation = host_rem
    criteria.append(host_criterion)

    # Judicial nuance (placeholder)
    jn_base = 1
    jn_opinions = synthesize_judicial_opinions_single("judicial_nuance", "Judicial Nuance", jn_base, [])
    jn_criterion = chief_justice(jn_opinions, "judicial_nuance", "Judicial Nuance")
    jn_criterion.remediation = REMEDIATION_BY_DIM["judicial_nuance"]
    criteria.append(jn_criterion)

    # Synthesis conflict resolution (placeholder)
    synth_base = 1
    synth_opinions = synthesize_judicial_opinions_single("synthesis_conflict_resolution", "Synthesis & Conflict Resolution", synth_base, [])
    synth_criterion = chief_justice(synth_opinions, "synthesis_conflict_resolution", "Synthesis & Conflict Resolution")
    synth_criterion.remediation = REMEDIATION_BY_DIM["synthesis_conflict_resolution"]
    criteria.append(synth_criterion)

    return criteria


# Audit report generator
def generate_audit_report(repo_url: str, criteria: List[CriterionResult]) -> AuditReport:
    def synthesize_judicial_opinions_flat(criteria_list: List[CriterionResult]) -> List[JudicialOpinion]:
        opinions: List[JudicialOpinion] = []
        for c in criteria_list:
            if c.judge_opinions:
                opinions.extend(c.judge_opinions)
            else:
                opinions.extend(synthesize_judicial_opinions_single(c.dimension_id, c.dimension_name, c.final_score, []))
        return opinions

    def build_remediation_plan(criteria_list: List[CriterionResult]) -> str:
        items = [f"{c.dimension_id}: {c.remediation}" for c in criteria_list if c.remediation]
        return "; ".join(items) if items else "No remediation suggested."

    overall = float(mean([float(c.final_score) for c in criteria])) if criteria else 0.0
    opinions = synthesize_judicial_opinions_flat(criteria)
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


# Markdown serializer (robust)
def serialize_report_to_markdown(report: AuditReport, output_path: str):
    if report is None:
        raise ValueError("serialize_report_to_markdown called with None report")

    lines: List[str] = []
    lines.append(f"# Audit Report for {report.repo_url}\n")
    lines.append(f"**Executive Summary:** {report.executive_summary}\n")
    pct = (report.overall_score / MAX_SCORE) * 100 if MAX_SCORE else 0
    lines.append(f"**Overall Score:** {report.overall_score:.2f} / {MAX_SCORE:.2f} — {pct:.0f}%\n")

    lines.append("\n## Criterion Breakdown\n")
    for c in report.criteria:
        lines.append(f"### {c.dimension_name} (Score: {c.final_score} / {MAX_SCORE})\n")

        # computed mean for transparency
        float_mean = None
        try:
            scores = []
            for op in c.judge_opinions or []:
                if isinstance(op, dict):
                    s = op.get("score", None)
                else:
                    s = getattr(op, "score", None)
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
                if isinstance(op, dict):
                    judge = op.get("judge", "Unknown")
                    score = op.get("score", None)
                    argument = op.get("argument", "")
                    cited = op.get("cited_evidence", None)
                else:
                    judge = getattr(op, "judge", "Unknown")
                    score = getattr(op, "score", None)
                    argument = getattr(op, "argument", "")
                    cited = getattr(op, "cited_evidence", None)

                score_display = "N/A" if score is None else str(int(score))
                lines.append(f"- **{judge}** ({score_display}): {argument}")
                if cited:
                    lines.append(f"  - Evidence: {', '.join(map(str, cited))}")
        else:
            lines.append("- No judge opinions recorded.")

        if getattr(c, "dissent_summary", None):
            lines.append(f"\n**Dissent:** {c.dissent_summary}")
        if getattr(c, "remediation", None):
            lines.append(f"\n**Remediation:** {c.remediation}\n")
        else:
            lines.append("\n**Remediation:** No remediation provided.\n")

    lines.append("\n## Remediation Plan\n")
    lines.append(report.remediation_plan or "No remediation provided.")

    # Ensure directory exists and replace any existing file atomically
    out_dir = os.path.dirname(output_path) or "."
    os.makedirs(out_dir, exist_ok=True)
    tmp_path = os.path.join(out_dir, f".tmp_{Path(output_path).name}")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    # remove existing file if present, then rename temp to final
    try:
        if os.path.exists(output_path):
            os.remove(output_path)
    except Exception:
        pass
    os.replace(tmp_path, output_path)


# Runner
def run_peer_audit(target_repo_url: str, source_repo_path: str):
    criteria = build_criteria_from_detectors(source_repo_path)
    report = generate_audit_report(target_repo_url, criteria)

    out_dir = "audit/report_peer_generated"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "peer-owner__peer-repo-audit.md")

    # serialize_report_to_markdown will replace any existing report atomically
    serialize_report_to_markdown(report, out_path)
    print(f"Peer audit written to {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m tests.test_peer_repo <target_repo_url> <source_repo_path>")
        sys.exit(1)
    run_peer_audit(sys.argv[1], sys.argv[2])
