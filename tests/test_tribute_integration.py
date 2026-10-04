"""跨局真实换牌、首出权和连续比赛回归。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collections import Counter
from unittest.mock import patch
from agents.rule_agent import RuleAgent
from game_engine.card import Card, Rank, Suit
from game_engine.deck import deal_hands
from game_engine.round_result import Player, judge_round_end
from game_engine.tribute import exchange_tribute
from game_series import GameSeries
from match_runner import Match


def c(rank, suit=Suit.SPADE):
    return Card(suit, Rank(rank))


def result(order=(0, 1, 2, 3)):
    return judge_round_end([Player(f'AI{i+1}', 'A' if i % 2 == 0 else 'B') for i in order])


def total(hands):
    return Counter(card for hand in hands.values() for card in hand)


def test_single_exchange_transfers_and_returns_cards():
    hands = {'AI1': [c(3), c(9)], 'AI2': [c(5)], 'AI3': [c(6)],
             'AI4': [c(14), c(2, Suit.HEART)]}
    before = total(hands)
    out = exchange_tribute(result(), hands, Rank.TWO)
    assert out.first_player.player_id == 'AI4'
    assert hands['AI1'] == [c(9), c(14)]
    assert hands['AI4'] == [c(2, Suit.HEART), c(3)]
    assert out.assignments[0].return_card == c(3)
    assert total(hands) == before


def test_double_exchange_larger_tribute_goes_to_head():
    hands = {'AI1': [c(3)], 'AI3': [c(4)], 'AI2': [c(13)], 'AI4': [c(14)]}
    before = total(hands)
    out = exchange_tribute(result((0, 2, 1, 3)), hands, Rank.TWO)
    assert out.first_player.player_id == 'AI4'
    assert hands == {'AI1': [c(14)], 'AI3': [c(13)], 'AI2': [c(4)], 'AI4': [c(3)]}
    assert total(hands) == before


def test_equal_double_tribute_uses_previous_third_place():
    hands = {'AI1': [c(3)], 'AI3': [c(4)], 'AI2': [c(14)], 'AI4': [c(14, Suit.CLUB)]}
    out = exchange_tribute(result((0, 2, 1, 3)), hands, Rank.TWO)
    assert out.first_player.player_id == 'AI2'
    assert out.assignments[0].receiver.player_id == 'AI1'


def test_single_and_double_anti_tribute_do_not_change_hands():
    big = c(16, Suit.JOKER)
    cases = [(result(), [big, big], [c(4)]),
             (result((0, 2, 1, 3)), [big], [big]),
             (result((0, 2, 1, 3)), [c(4)], [big, big])]
    for previous, fourth, second in cases:
        hands = {'AI1': [c(3)], 'AI3': [c(4)], 'AI2': second, 'AI4': fourth}
        before = {k: list(v) for k, v in hands.items()}
        out = exchange_tribute(previous, hands, Rank.TWO)
        assert out.anti_tribute and not out.assignments
        assert out.first_player.player_id == 'AI1' and hands == before


def test_round_level_overrides_team_progress_for_tribute():
    wild = c(5, Suit.HEART)
    hands = {'AI1': [c(5), c(3)], 'AI2': [c(4)], 'AI3': [c(6)],
             'AI4': [wild, wild, c(5, Suit.CLUB), c(7, Suit.CLUB), c(14)]}
    out = exchange_tribute(result(), hands, Rank.FIVE, {'A': Rank.FIVE, 'B': Rank.SEVEN})
    assert out.assignments[0].tribute_card == c(5, Suit.CLUB)
    assert out.assignments[0].return_card == c(3)
    assert hands['AI4'].count(wild) == 2


def test_failed_return_leaves_all_original_hands_unchanged():
    hands = {'AI1': [c(3)], 'AI3': [c(14)], 'AI2': [c(13)], 'AI4': [c(14)]}
    before = {k: list(v) for k, v in hands.items()}
    try:
        exchange_tribute(result((0, 2, 1, 3)), hands, Rank.TWO)
    except ValueError:
        pass
    else:
        raise AssertionError('必须拒绝无合法还贡牌的交换')
    assert hands == before


def test_match_prepare_is_idempotent_and_run_does_not_redeal():
    messages = []
    match = Match([RuleAgent(f'AI{i+1}') for i in range(4)], seed=42, verbose=False,
                  previous_result=result(), event_callback=messages.append)
    dealt = deal_hands(seed=42)
    before = Counter(card for hand in dealt for card in hand)
    with patch('match_runner.deal_hands', return_value=dealt) as deal:
        match.prepare()
        saved = [list(hand) for hand in match.hands]
        match.prepare()
        assert match.hands == saved
        assert all(len(hand) == 27 for hand in saved)
        assert Counter(card for hand in saved for card in hand) == before
        assert match.current_player == int(match.tribute_outcome.first_player.player_id[-1]) - 1
        assert any('首出' in m for m in messages)
        match.run()
        assert deal.call_count == 1 and len(match.finish_order) == 4


def test_series_passes_previous_result_after_upgrade_and_completes():
    for seed in range(5):
        messages = []
        series = GameSeries([RuleAgent(f'AI{i+1}') for i in range(4)], seed=seed,
                            verbose=False, event_callback=messages.append)
        series.run(max_rounds=100)
        assert series.finished and len(series.history) > 1
        assert sum('本局首出' in m for m in messages) == len(series.history) - 1
        assert any('进贡' in m or '抗贡' in m for m in messages)


def test_return_ten_allowed_even_if_not_smaller_than_tribute():
    from game_engine.tribute import TributeAssignment, apply_return_tribute
    assignment = TributeAssignment(Player('a', 'A'), Player('b', 'B'), c(3))
    for rank in range(2, 11):
        apply_return_tribute(assignment, c(rank), Rank.TEN)
        assert assignment.return_card == c(rank)
    for card in [c(rank) for rank in range(11, 15)] + [c(15, Suit.JOKER), c(16, Suit.JOKER)]:
        try:
            apply_return_tribute(assignment, card, Rank.TWO)
        except ValueError:
            pass
        else:
            raise AssertionError('大于10的牌不能还贡')


def test_a_plays_five_then_b_wins_one_level_and_table_plays_three():
    agents = [RuleAgent(f'AI{i+1}') for i in range(4)]
    series = GameSeries(agents, verbose=False)
    a_double = result((0, 2, 1, 3))
    b_one = result((1, 0, 2, 3))
    seen = []
    def finish(match):
        seen.append(match.level_rank)
        return a_double if len(seen) == 1 else b_one
    with patch.object(Match, 'run', finish):
        series.play_round()
        assert series.team_levels == {'A': Rank.FIVE, 'B': Rank.TWO}
        assert series.level_rank == Rank.FIVE
        series.play_round()
        assert seen == [Rank.TWO, Rank.FIVE]
        assert series.team_levels == {'A': Rank.FIVE, 'B': Rank.THREE}
        assert series.level_rank == Rank.THREE
    match = Match(agents, level_rank=series.level_rank, team_levels=series.team_levels, verbose=False)
    match.prepare()
    assert all(match._build_observation(i).level_rank == Rank.THREE for i in range(4))


def test_b_uses_shared_five_for_tribute_wildcards_and_play_power():
    from game_engine.card import LEVEL_RANK_POWER
    match = Match([RuleAgent(f'AI{i+1}') for i in range(4)], level_rank=Rank.FIVE,
                  team_levels={'A': Rank.FIVE, 'B': Rank.TWO}, verbose=False)
    match.hands = [[c(4)], [c(5), c(2), c(5, Suit.HEART)], [c(6)], [c(7)]]
    obs = match._build_observation(1)
    assert obs.level_rank == Rank.FIVE
    match._handle_play(1, [c(5)])
    assert match.last_play.power == LEVEL_RANK_POWER
    match.last_play = None
    match._handle_play(1, [c(2), c(5, Suit.HEART)])
    assert match.last_play.power == 2 and match.last_play.wildcards_used == [c(5, Suit.HEART)]
    hands = {'AI1': [c(3)], 'AI2': [c(2), c(5), c(5, Suit.HEART)],
             'AI3': [c(4)], 'AI4': [c(2, Suit.CLUB), c(5, Suit.CLUB)]}
    out = exchange_tribute(result((0, 2, 1, 3)), hands, Rank.FIVE,
                           {'A': Rank.FIVE, 'B': Rank.TWO})
    assert all(a.tribute_card.rank == Rank.FIVE for a in out.assignments)
    assert c(5, Suit.HEART) in hands['AI2']


def test_interactive_tribute_waits_validates_and_conserves_cards():
    from game_engine.tribute import TributeSession
    hands = {'AI1': [c(14), c(2), c(2, Suit.HEART)], 'AI2': [c(3)],
             'AI3': [c(4)], 'AI4': [c(5)]}
    previous = result((1, 3, 2, 0))
    before = total(hands)
    session = TributeSession(previous, hands, Rank.TWO, 'AI1')
    assert session.pending[0] == 'tribute' and session.actor() == 'AI1'
    snapshot = {k: list(v) for k,v in hands.items()}
    try:
        session.submit(c(2, Suit.HEART))
    except ValueError:
        pass
    else:
        raise AssertionError('红心级牌不能进贡')
    assert hands == snapshot
    session.submit(c(2))
    assert session.complete and total(hands) == before
    assert len(hands['AI1']) == 3


def test_interactive_return_waits_and_accepts_ten():
    from game_engine.tribute import TributeSession
    hands = {'AI1': [c(10), c(14)], 'AI2': [c(3)], 'AI3': [c(4)], 'AI4': [c(13)]}
    before = total(hands)
    session = TributeSession(result(), hands, Rank.TWO, 'AI1')
    assert session.pending[0] == 'return' and len(hands['AI1']) == 3
    snapshot = {k: list(v) for k,v in hands.items()}
    try:
        session.submit(c(14))
    except ValueError:
        pass
    else:
        raise AssertionError('不能还A')
    assert hands == snapshot
    session.submit(c(10))
    assert session.complete and hands['AI4'] == [c(10)]
    assert total(hands) == before and len(hands['AI1']) == 2


def test_match_blocks_play_until_human_tribute_completed():
    match = Match([RuleAgent(f'AI{i+1}') for i in range(4)], verbose=False,
                  previous_result=result())
    hands = [[c(10), c(14)], [c(3)], [c(4)], [c(13)]]
    with patch('match_runner.deal_hands', return_value=hands):
        match.prepare(interactive_player='AI1')
    assert match.tribute_pending
    try:
        match._take_turn()
    except Exception as exc:
        assert '进贡' in str(exc)
    else:
        raise AssertionError('交换前不得出牌')
    match.submit_tribute(c(10))
    assert not match.tribute_pending and match.current_player == 3
