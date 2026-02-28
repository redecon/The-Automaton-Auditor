from typing import List
from src.state import Evidence

def evidence_aggregator(evidences: List[Evidence]) -> List[Evidence]:
    """
    Aggregate evidence from all detectives into a structured list.
    - Deduplicates by goal (last one wins).
    - Always returns a List[Evidence] to satisfy AgentState schema.
    """
    aggregated = {}
    for ev in evidences:
        aggregated[ev.goal] = ev  # overwrite duplicates by goal

    # Return as a list of Evidence objects
    return list(aggregated.values())
