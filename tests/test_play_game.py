"""Offline controller contracts usable by a touch UI without Tk."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.rule_agent import RuleAgent
from play_game import PlayGame


def test_play_game_import_has_no_ui_or_llm_dependencies():
    code = """
import sys
from play_game import PlayGame
game = PlayGame()
game.new_game()
assert not any(name.startswith(('tkinter', 'llm_', 'agents.llm', 'agents.deepseek', 'agents.lmstudio', 'benchmark')) for name in sys.modules)
"""
    subprocess.run([sys.executable, '-B', '-c', code], check=True,
                   cwd=Path(__file__).resolve().parent.parent)


def test_play_game_snapshot_is_json_and_detached():
    game = PlayGame()
    game.new_game(seed=42)
    state = json.loads(json.dumps(game.snapshot()))
    assert all(len(hand) == 27 for hand in state['hands'])
    assert [c['index'] for c in state['hands'][0]] == list(range(27))
    state['hands'][0].clear()
    state['team_levels']['A'] = 14
    assert len(game.match.hands[0]) == 27
    assert game.snapshot()['team_levels']['A'] == 2
    assert game.drain_events()
    assert game.drain_events() == []


def human_turn_game():
    game = PlayGame()
    game.new_game(human_mode=True, seed=101)
    for _ in range(100):
        if game.human_can_play:
            return game
        assert game.step()
    raise AssertionError('Human never received a turn')


def test_play_game_waits_for_human_and_validates_indices():
    game = human_turn_game()
    before = game.snapshot()
    assert not game.step()
    for indices in ([], [0, 0], [-1], [999], [True]):
        try:
            game.play(indices)
        except ValueError:
            pass
        else:
            raise AssertionError(f'Accepted invalid selection: {indices}')
        assert game.snapshot() == before
    cards = game.match.hands[0]
    action = RuleAgent('test').decide(game.match._build_observation(0))
    if action.action_type == 'pass':
        game.pass_turn()
    else:
        game.play([next(i for i, c in enumerate(cards) if c is selected)
                   for selected in action.cards])
    assert game.turns == before['turns'] + 1


def test_play_game_rejects_human_actions_in_observer_mode():
    game = PlayGame()
    game.new_game(seed=42)
    before = game.snapshot()
    for action in (lambda: game.play([0]), game.pass_turn, lambda: game.exchange(0)):
        try:
            action()
        except ValueError:
            pass
        else:
            raise AssertionError('Accepted human action in observer mode')
    assert game.snapshot() == before


def test_play_game_mobile_actions_complete_series_and_exchanges():
    game = PlayGame()
    game.new_game(human_mode=True, seed=101)
    counts = {'play': 0, 'pass': 0, 'tribute': 0, 'return': 0}
    for _ in range(20000):
        state = game.snapshot()
        if state['series_finished']:
            break
        if state['pending_exchange']:
            counts[state['pending_exchange']] += 1
            game.exchange(state['eligible_exchange_indices'][0])
        elif state['human_can_play']:
            m = game.match
            action = RuleAgent('test').decide(m._build_observation(0))
            if action.action_type == 'pass':
                game.pass_turn()
                counts['pass'] += 1
            else:
                game.play([next(i for i, c in enumerate(m.hands[0]) if c is chosen)
                           for chosen in action.cards])
                counts['play'] += 1
        else:
            assert game.step()
        game.drain_events()
    else:
        raise AssertionError('Series did not finish')
    assert all(counts.values()), counts
    assert game.round_number > 1
    assert max(state['team_levels'].values()) == 14
    final = game.snapshot()
    assert not game.step()
    assert game.snapshot() == final
    game.new_game(human_mode=False, seed=42)
    assert game.round_number == 1 and not game.series_finished and not game.human_mode
    assert game.turns == 0 and game.match.tribute_outcome is None
