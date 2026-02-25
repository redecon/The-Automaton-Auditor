from src.state import Evidence

def evidence_aggregator(evidences: list[Evidence]) -> dict:
    """Aggregate evidence from all detectives into a structured dict."""
    aggregated = {}
    for ev in evidences:
        aggregated[ev.goal] = ev
    return aggregated
