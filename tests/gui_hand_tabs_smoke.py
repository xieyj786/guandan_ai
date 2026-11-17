"""Real Tk checks for GUI hand tabs and public key-card stacks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tkinter as tk
from unittest.mock import patch
from gui import GuandanGUI
from play import GuandanPlay
from game_engine.card import Card, Rank, Suit
from game_engine.deck import build_deck

def check_hand_tabs(app_class):
    root = tk.Tk()
    gui = app_class(root)
    root.update()
    assert not gui.key_cards_tab.winfo_ismapped()
    for seat in range(4):
        gui.hand_tabs[seat].invoke(); root.update()
        assert len(gui.hand_tiles) == len(gui.match.hands[seat])
        assert sorted((tile.suit, tile.rank) for tile in gui.hand_tiles) == sorted(
            (c.suit.value, int(c.rank)) for c in gui.match.hands[seat])
    assert all(button.winfo_ismapped() for button in gui.hand_tabs)
    gui.start_human_game()
    gui._pause(); root.update()
    assert gui.key_cards_tab.winfo_ismapped()
    assert not any(button.winfo_ismapped() for button in gui.hand_tabs[1:])
    selected = gui.match.hands[0][0]
    gui.selected_cards = [selected]
    gui.match.played_cards = build_deck()
    gui.key_cards_tab.invoke(); root.update()
    assert list(map(len, gui.key_card_groups)) == [2, 2, 8, 8, 8, 8]
    assert gui.selected_cards == [selected]
    for title, tiles in gui.key_columns:
        assert len({tile.winfo_x() for tile in tiles}) <= 1
        assert len({tile.winfo_y() for tile in tiles}) == len(tiles)
        assert all(tile.winfo_x() >= 0 and tile.winfo_x() + tile.winfo_width() <= gui.key_canvas.winfo_width() for tile in tiles)
    gui.key_canvas.yview_moveto(1); root.update()
    assert gui.key_canvas.yview()[1] == 1
    for level in (Rank.ACE, Rank.TEN, Rank.FIVE):
        gui.match.level_rank = level; gui._draw_hand(); root.update()
        assert list(map(len, gui.key_card_groups)) == [2, 2, 8, 8, 8, 8]
    gui.hand_tabs[0].invoke(); root.update()
    assert gui.selected_cards == [selected]
    assert sum(tile.selected for tile in gui.hand_tiles) == 1
    gui.new_game(human_mode=True); gui._pause(); root.update()
    gui.key_cards_tab.invoke(); root.update()
    assert not any(gui.key_card_groups)
    gui.new_game(); root.update()
    assert not gui.key_cards_tab.winfo_ismapped()
    assert all(button.winfo_ismapped() for button in gui.hand_tabs)
    gui._pause()
    while len(gui.match.finish_order) < 4:
        gui.match.take_turn()
    if isinstance(gui, GuandanPlay):
        gui.game._finish_round()
        gui._sync_game()
    else:
        gui._finish_round_if_needed()
    summary = gui.status.cget('text')
    assert '本局结束' in summary
    with patch.object(root, 'after', wraps=root.after) as schedule:
        gui._continue_human()
        assert any(call.args == (3000, gui.step) for call in schedule.call_args_list)
    assert gui.status.cget('text') == summary
    gui._pause()
    gui._advance_one()
    assert gui.round_number == 2
    with patch.object(root, 'after', wraps=root.after) as schedule:
        gui._continue_human()
        assert any(call.args == (900, gui.step) for call in schedule.call_args_list)
    gui.close()

for app_class in (GuandanGUI, GuandanPlay):
    check_hand_tabs(app_class)
    print(app_class.__name__, "hand tabs OK", flush=True)
print('PASS: observer seats, human-only key tab, duplicate counts, printed ranks, selection, scroll, reset')
