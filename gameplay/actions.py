"""Common legal action contract for humans, rule policies and LLM adapters."""
from gameplay.contracts import Action, Observation
from game_engine.legal_moves import legal_moves


def legal_actions(obs: Observation) -> list[Action]:
    actions = [Action('play', move.cards) for move in legal_moves(
        obs.hand, obs.level_rank, obs.use_wildcards, obs.last_play)]
    if obs.last_play is not None:
        actions.append(Action('pass'))
    return actions
