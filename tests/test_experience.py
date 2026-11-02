from pathlib import Path
from tempfile import TemporaryDirectory
import json
from unittest.mock import patch

from evaluation.experience import append_case, decode_case, evaluate_cases, make_case, same_action
from game_engine.card import Card, Rank, Suit
from gameplay.contracts import Action, Observation
from strategy.rule_agent import RuleAgent


def observation():
    return Observation(hand=[Card(Suit.SPADE, Rank.THREE), Card(Suit.CLUB, Rank.FOUR)],
                       level_rank=Rank.TWO, last_play=None, teammate_hand_size=5,
                       opponent_hand_sizes=(5, 5))


def test_experience_roundtrip_and_draft_is_not_a_target():
    obs = observation()
    action = RuleAgent('test').decide(obs)
    case = make_case('lead-001', obs, action, source='llm', note='待复核', reference='round-1/turn-1')
    restored, selected = decode_case(json.loads(json.dumps(case)))
    assert restored == obs and same_action(selected, action)
    with TemporaryDirectory() as directory:
        path = Path(directory) / 'cases.jsonl'
        append_case(path, case)
        assert evaluate_cases(path, RuleAgent) == []
        case['case_id'] = 'reviewed-001'
        case['approved'] = True
        append_case(path, case)
        result = evaluate_cases(path, RuleAgent)
        assert result == [dict(case_id='reviewed-001', agrees=True, legal=True)]
        assert len(path.read_text().splitlines()) == 2


def test_experience_illegal_preference_and_foreign_card_are_rejected():
    obs = observation()
    for action in (Action('pass'), Action('play', [Card(Suit.HEART, Rank.ACE)])):
        try:
            make_case('bad', obs, action, source='human')
        except ValueError:
            pass
        else:
            raise AssertionError('Accepted an illegal or unobserved action')
    case = make_case('good', obs, Action('play', [obs.hand[0]]), source='human')
    case['action']['indices'] = [True]
    try:
        decode_case(case)
    except ValueError:
        pass
    else:
        raise AssertionError('Boolean hand index accepted')


def test_legal_llm_candidates_do_not_depend_on_rule_policy():
    from gameplay.actions import legal_actions
    from integrations.llm.deepseek_agent import DeepSeekAgent
    obs = observation()
    expected = legal_actions(obs)
    with patch.object(RuleAgent, '_beats', side_effect=AssertionError('strategy used for legality')):
        actual = DeepSeekAgent('llm', object()).candidates(obs)
    assert len(actual) == len(expected)
    assert all(same_action(a, b) for a, b in zip(actual, expected))
