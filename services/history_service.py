"""
Player history service.

Responsible for building a per-player round history so the frontend
can render authoritative payoff logs directly from the server.
"""
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from models import Action, Round
from services.pairing_service import get_opponent_id


def get_player_round_history(room_id: str, player_id: str, db: Session) -> List[Dict[str, Any]]:
    """
    Return an ordered list of rounds (round 1..N) where the player
    already has a calculated payoff.

    Each entry contains both players' choices and payoffs so the frontend
    can show the complete record without relying on client-side storage.
    """
    rows = (
        db.query(Action, Round.round_number)
        .join(Round, Action.round_id == Round.id)
        .filter(Action.room_id == room_id, Action.player_id == player_id)
        .order_by(Round.round_number)
        .all()
    )

    history: List[Dict[str, Any]] = []

    for action, round_number in rows:
        if action.payoff is None:
            # Result not published yet, skip to mimic previous behavior.
            continue

        entry: Dict[str, Any] = {
            "round_number": round_number,
            "your_choice": action.choice,
            "your_payoff": action.payoff,
        }

        try:
            opponent_id = get_opponent_id(action.round_id, player_id, db)
            opponent_action = (
                db.query(Action)
                .filter(Action.round_id == action.round_id, Action.player_id == opponent_id)
                .first()
            )
            if opponent_action:
                entry["opponent_choice"] = opponent_action.choice
                entry["opponent_payoff"] = opponent_action.payoff
                entry["opponent_display_name"] = (
                    opponent_action.player.display_name if opponent_action.player else None
                )
        except ValueError:
            # No opponent yet (shouldn't happen after payoff exists) but keep structure valid.
            entry["opponent_choice"] = None
            entry["opponent_payoff"] = None
            entry["opponent_display_name"] = None

        history.append(entry)

    return history
