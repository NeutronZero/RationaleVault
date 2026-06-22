from __future__ import annotations


def calculate_degradation(
    initial_continuity: float,
    final_continuity: float,
    handoff_count: int,
) -> float:
    if handoff_count <= 0:
        return 0.0
    return (initial_continuity - final_continuity) / handoff_count


def calculate_event_rates(
    generated: int,
    accepted: int,
    rejected: int,
    edited: int,
) -> dict[str, float]:
    if generated <= 0:
        return {
            "human_edit_rate": 0.0,
            "human_reject_rate": 0.0,
            "auto_accept_rate": 0.0,
        }
    return {
        "human_edit_rate": edited / generated,
        "human_reject_rate": rejected / generated,
        "auto_accept_rate": accepted / generated,
    }
