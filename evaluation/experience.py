"""Reviewed decision cases for turning real play experience into regressions.

Cases never execute code or change a live strategy. A recorded LLM decision is
an observation to review, not automatically a preferred action.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from game_engine.card import Card, Rank, Suit
from game_engine.card_type import CardType, CardTypeCategory
from gameplay.actions import legal_actions
from gameplay.contracts import Action, Observation

SCHEMA_VERSION = 1


def make_case(case_id: str, observation: Observation, action: Action, *, source: str,
              note: str = '', reference: str = '', approved: bool = False,
              decision_kind: str | None = None, strategy_version: str = '', outcome: str = 'unknown') -> dict:
    """Capture only the actor's observation and selected action; no full table/client."""
    if source not in ('human', 'llm', 'rule'):
        raise ValueError('source must be human, llm or rule')
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError('case_id is required')
    indices = []
    used = set()
    for selected in action.cards:
        index = next((i for i, card in enumerate(observation.hand)
                      if i not in used and card is selected), None)
        if index is None:
            raise ValueError('action must reference actual cards in the observed hand')
        indices.append(index)
        used.add(index)
    decision_kind = decision_kind or source
    data = asdict(observation)
    def card_data(card):
        return {'suit': card.suit.value, 'rank': int(card.rank)}
    data['hand'] = [card_data(c) for c in observation.hand]
    data['played_cards'] = [card_data(c) for c in observation.played_cards]
    data['level_rank'] = int(observation.level_rank)
    last = observation.last_play
    data['last_play'] = (dict(category=last.category.name, cards=[card_data(c) for c in last.cards],
                              power=last.power, length=last.length) if last else None)
    case = dict(schema_version=SCHEMA_VERSION, case_id=case_id, source=source,
                note=note, reference=reference, approved=approved, decision_kind=decision_kind,
                strategy_version=strategy_version, outcome=outcome,
                observation=data, action=dict(action_type=action.action_type, indices=indices))
    decode_case(case)  # Validate legality before accepting a proposed preference.
    return case


def decode_case(case: dict) -> tuple[Observation, Action]:
    if (case.get('schema_version') != SCHEMA_VERSION
            or case.get('source') not in ('human', 'llm', 'rule')
            or case.get('decision_kind') not in ('human', 'rule', 'llm', 'automatic', 'fallback')
            or case.get('outcome') not in ('unknown', 'win', 'loss')
            or type(case.get('approved')) is not bool
            or not isinstance(case.get('case_id'), str) or not case['case_id'].strip()):
        raise ValueError('invalid decision case metadata')
    def card(raw):
        return Card(Suit(raw['suit']), Rank(raw['rank']))
    data = dict(case['observation'])
    data['hand'] = [card(c) for c in data['hand']]
    data['played_cards'] = [card(c) for c in data['played_cards']]
    data['level_rank'] = Rank(data['level_rank'])
    data['opponent_hand_sizes'] = tuple(data['opponent_hand_sizes'])
    last = data['last_play']
    if last is not None:
        data['last_play'] = CardType(category=CardTypeCategory[last['category']],
                                    cards=[card(c) for c in last['cards']],
                                    power=last['power'], length=last['length'])
    observation = Observation(**data)
    raw_action = case['action']
    indices = raw_action['indices']
    if (not isinstance(indices, list) or any(type(i) is not int or not 0 <= i < len(observation.hand) for i in indices)
            or len(set(indices)) != len(indices)):
        raise ValueError('invalid hand indices')
    action = Action(raw_action['action_type'], [observation.hand[i] for i in indices])
    if not any(same_action(action, candidate) for candidate in legal_actions(observation)):
        raise ValueError('recorded action is illegal in this observation')
    return observation, action


def same_action(left: Action, right: Action) -> bool:
    return left.action_type == right.action_type and Counter(left.cards) == Counter(right.cards)


def append_case(path: str | Path, case: dict):
    decode_case(case)
    line = json.dumps(case, ensure_ascii=False, allow_nan=False)
    with Path(path).open('a', encoding='utf-8') as stream:
        stream.write(line + '\n')


def evaluate_cases(path: str | Path, agent_factory) -> list[dict]:
    """Compare approved preferences only; agreement is not a win-rate estimate."""
    results = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        observation, expected = decode_case(case)
        if not case['approved']:
            continue
        actual = agent_factory('experience-check').decide(observation)
        results.append(dict(case_id=case['case_id'], agrees=same_action(actual, expected),
                            legal=any(same_action(actual, candidate) for candidate in legal_actions(observation))))
    return results
