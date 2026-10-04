"""最后一手未被压住时队友接风，包括队友主动压牌的边界。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.rule_agent import RuleAgent
from game_engine.card import Card, Rank, Suit
from match_runner import Match
from turn_log import format_turn_log


def card(r):
    return Card(Suit.JOKER if r >= 15 else Suit.SPADE, Rank(r))


def setup(last=16):
    m = Match([RuleAgent(f'AI{i+1}') for i in range(4)], verbose=False)
    m.hands = [[card(3)], [card(4)], [card(last)], [card(5)]]
    m.current_player = 2
    m._handle_play(2, [card(last)])
    return m


def test_ai3_big_joker_everyone_passes_ai1_receives_wind():
    m = setup()
    for seat in (3, 0):
        assert m.current_player == seat
        m._handle_pass(seat)
        assert m.last_play is not None
    m._handle_pass(1)
    assert m.current_player == 0 and m.last_play is None and m.pass_streak == 0
    assert any('AI1 接风' in s for s in format_turn_log(m, 1, 1, 4))


def test_opponent_bomb_cancels_original_wind():
    m = setup()
    bomb = [card(6), card(6), Card(Suit.CLUB, Rank.SIX), Card(Suit.CLUB, Rank.SIX)]
    m.hands[3] = bomb + [card(9)]
    m._handle_play(3, bomb)
    m._handle_pass(0)
    m._handle_pass(1)
    assert m.current_player == 3 and m.last_play is None


def test_teammate_can_cover_then_new_winner_controls():
    m = setup(9)
    m.hands[0] = [card(10), card(3)]
    m._handle_pass(3)
    m._handle_play(0, [card(10)])
    m._handle_pass(1)
    m._handle_pass(3)
    assert m.current_player == 0 and m.last_player == 0


def test_covering_player_finishes_own_teammate_receives_wind():
    m = setup(9)
    m.hands[3] = [card(10)]
    m._handle_play(3, [card(10)])
    m._handle_pass(0)
    m._handle_pass(1)
    assert m.current_player == 1 and m.last_play is None


def test_finished_teammate_falls_back_to_next_active():
    m = setup()
    m.hands[0] = []
    m.finish_order.insert(0, 0)
    m._handle_pass(3)
    m._handle_pass(1)
    assert m.current_player == 3 and m.last_play is None
