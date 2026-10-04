"""
终局判定 + 进贡/抗贡/还贡 的单元测试骨架。
牌型识别相关测试（含缺口填补）留待 identify.py 实现后补充。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game_engine.card import Card, Rank, Suit
from game_engine.comparator import compare_card_type
from game_engine.identify import identify_card_type
from game_engine.round_result import Player, judge_round_end, TributeType
from game_engine.tribute import (
    check_anti_tribute,
    determine_tribute_card,
    resolve_tribute,
    apply_return_tribute,
)

LEVEL = Rank.TWO if hasattr(Rank, "TWO") else Rank.THREE  # 占位，实际按当前级牌配置


def make_players():
    return [
        Player("P1", "A"), Player("P2", "B"),
        Player("P3", "A"), Player("P4", "B"),
    ]


def test_double_down_upgrade_3():
    p1, p2, p3, p4 = make_players()
    # 头游P1(A队)，二游P3(A队) 同队 -> 双下，升3级
    result = judge_round_end([p1, p3, p2, p4])
    assert result.upgrade_level == 3
    assert result.tribute_type == TributeType.DOUBLE
    assert set(x.player_id for x in result.tribute_players) == {"P2", "P4"}


def test_single_down_third_place_upgrade_2():
    p1, p2, p3, p4 = make_players()
    # 头游P1(A)，三游P2... 需要保证第三名与头游同队
    # finish_order: [头游, 二游, 三游, 末游]
    result = judge_round_end([p1, p2, p3, p4])
    # p1=A, p3=A (third place), same team -> upgrade 2
    assert result.upgrade_level == 2
    assert result.tribute_type == TributeType.SINGLE
    assert result.tribute_players[0].player_id == "P4"


def test_single_down_last_place_upgrade_1():
    p1, p2, p3, p4 = make_players()
    # 头游P1(A), 末游P3(A) 同队 -> 升1级
    result = judge_round_end([p1, p2, p4, p3])
    assert result.upgrade_level == 1
    assert result.tribute_players[0].player_id == "P3"


def test_anti_tribute_single_two_big_jokers():
    p4 = Player("P4", "B")
    hands = {"P4": [Card(Suit.JOKER, Rank.BIG_JOKER), Card(Suit.JOKER, Rank.BIG_JOKER)]}
    assert check_anti_tribute([p4], hands) is True


def test_anti_tribute_double_each_one_big_joker():
    p2 = Player("P2", "B")
    p4 = Player("P4", "B")
    hands = {
        "P2": [Card(Suit.JOKER, Rank.BIG_JOKER)],
        "P4": [Card(Suit.JOKER, Rank.BIG_JOKER)],
    }
    assert check_anti_tribute([p2, p4], hands) is True


def test_tribute_card_hearts_level_protection():
    level_rank = Rank.TWO
    hand = [
        Card(Suit.HEART, Rank.TWO),   # 红心级牌，受保护
        Card(Suit.SPADE, Rank.ACE),   # 次大牌
    ]
    card = determine_tribute_card(hand, level_rank)
    assert card == Card(Suit.SPADE, Rank.ACE)


def test_return_tribute_must_be_at_most_ten():
    from game_engine.tribute import TributeAssignment

    level_rank = Rank.TWO
    assignment = TributeAssignment(
        giver=Player("P4", "B"), receiver=Player("P1", "A"),
        tribute_card=Card(Suit.SPADE, Rank.ACE),
    )
    try:
        apply_return_tribute(assignment, Card(Suit.SPADE, Rank.ACE), level_rank)
        assert False, "应拒绝大于10的还贡牌"
    except ValueError:
        pass

    apply_return_tribute(assignment, Card(Suit.CLUB, Rank.THREE), level_rank)
    assert assignment.return_card == Card(Suit.CLUB, Rank.THREE)


def test_single_card_type_uses_single_card_power():
    level_rank = Rank.TWO
    ace = identify_card_type([Card(Suit.SPADE, Rank.ACE)], level_rank)
    level = identify_card_type([Card(Suit.CLUB, Rank.TWO)], level_rank)
    assert compare_card_type(level, ace, level_rank) == 1


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
