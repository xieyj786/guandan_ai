"""随机模式、复现记录和界面配置隔离。"""
from unittest.mock import patch
from collections import Counter
import json
from gameplay.randomness import SeedSequence, NORMAL, REPLAY
from gameplay.offline import PlayGame
from gameplay.match import Match
from game_engine.deck import build_deck, deal_opening
from strategy.rule_agent import RuleAgent


def test_normal_mode_independent_system_seeds_and_replay():
    with patch("gameplay.randomness.secrets.randbits", side_effect=[123, 987, 456]) as source:
        game = PlayGame()
        game.new_game()
        assert game.randomness.mode == NORMAL
        assert game.match.seed == 123
        assert game.match.hands == deal_opening(123).hands
        game._start_round()
        assert game.match.seed == 987
        game.new_game()
        assert game.match.seed == 456
        assert len(game.round_records) == 1
        assert source.call_count == 3


def test_fixed_series_and_normal_record_can_be_replayed():
    with patch("gameplay.randomness.secrets.randbits", side_effect=AssertionError("unexpected system RNG")):
        game = PlayGame()
        game.new_game(seed=0)
        assert game.randomness.mode == REPLAY
        first = game.match.hands
        game._start_round()
        assert [r["seed"] for r in game.round_records] == [0, 1]
        game.new_game(seed=0)
        assert game.match.hands == first
        assert Counter(c for h in first for c in h) == Counter(build_deck())
        record = json.loads(json.dumps(game.round_records[0]))
        assert record["hands_before_tribute"] == [[[c.suit.value, int(c.rank)] for c in h] for h in first]
        assert record["first_player"] == game.match.current_player


def test_match_resolves_and_records_unspecified_seed_only_once():
    with patch("gameplay.randomness.secrets.randbits", return_value=900) as source:
        match = Match([RuleAgent(str(i)) for i in range(4)], verbose=False)
        match.prepare(); match.prepare()
        assert source.call_count == 1
        assert match.seed == match.deal_record["seed"] == 900
        assert match.hands == deal_opening(900).hands


def test_ui_choice_is_frozen_for_current_series():
    # Exercise the actual UI selection method without needing a display.
    from presentation.random_controls import RandomControls
    class Value:
        def __init__(self, value): self.value = value
        def get(self): return self.value
    control = object.__new__(RandomControls)
    control.mode = Value(REPLAY); control.seed = Value("42")
    active = control.selection()
    control.seed.value = "bad"; control.mode.value = NORMAL
    assert active.for_round(2) == 43
    assert control.selection().base_seed is None  # Ignore hidden seed in normal mode.
    control.mode.value = REPLAY
    try:
        control.selection()
    except ValueError:
        pass
    else:
        raise AssertionError("invalid test seed accepted")
