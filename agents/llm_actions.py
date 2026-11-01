"""Shared legal move set for all LLM adapters."""
from agents.base import Action, Observation
from agents.rule_agent import RuleAgent
from game_engine.moves import generate_all_moves

def legal_actions(obs: Observation) -> list[Action]:
    moves = generate_all_moves(obs.hand, obs.level_rank, use_wildcards=obs.use_wildcards,
                               last_play=obs.last_play)
    actions = [Action('play', m.cards) for m in moves if obs.last_play is None or
               RuleAgent._beats(m, obs.last_play, obs.level_rank)]
    if obs.last_play is not None:
        actions.append(Action('pass'))
    return actions
