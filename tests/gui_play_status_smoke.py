"""真实 Tk 验证等待、上一手保留、PASS 和游次；不调用网络。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tkinter as tk
from unittest.mock import patch
from gui import GuandanGUI
from llm_settings import LLMSettings

root = tk.Tk()
with patch.object(LLMSettings, 'load', return_value=LLMSettings()):
    gui = GuandanGUI(root)
root.update()
assert all(gui._play_display_state(i)[0] == '等待出牌' for i in range(4))
seen_pass = seen_finish = seen_reclaim = False
for _ in range(400):
    m = gui.match
    actor = m.current_player
    previous_cards = [list(h) for h in gui.player_cards]
    previous_last = m.last_play
    gui.single_step()
    root.update()
    if gui.match is not m:
        break
    states = [gui._play_display_state(i) for i in range(4)]
    if len(m.finish_order) == 4:
        assert not any(status == '等待出牌' for status, _ in states)
        assert gui.pending_round_result is not None
    else:
        assert sum(status == '等待出牌' for status, _ in states) == 1
        assert states[m.current_player][0] == '等待出牌'
    for i in range(4):
        if i != actor:
            assert gui.player_cards[i] == previous_cards[i]
        if i in m.finish_order:
            seen_finish = True
            assert states[i][0] == ('头游','二游','三游','末游')[m.finish_order.index(i)]
            assert states[i][1] == gui.player_cards[i]
            assert gui.play_faces[i].cards == [(c.suit.value, int(c.rank)) for c in gui.player_cards[i]]
        if states[i][0] == 'PASS':
            seen_pass = True
            strip = gui.play_faces[i]
            assert strip.status_text == 'PASS' and not strip.cards
            texts = [strip.itemcget(item, 'text') for item in strip.find_all() if strip.type(item) == 'text']
            assert texts == ['PASS']
            button = gui.control_buttons['新局']
            x1, y1, x2, y2 = strip.coords('status_box')
            from tkinter import ttk, font as tkfont
            status_font = ttk.Style(root).lookup(button.cget('style') or 'TButton', 'font') or 'TkDefaultFont'
            assert abs((x2-x1+1) - tkfont.Font(root, font=status_font).measure('MMMMM')) < .01
            assert abs((y2-y1+1) - button.winfo_height()) < .01
            from tkinter import ttk, font as tkfont
            expected = ttk.Style(root).lookup(button.cget('style') or 'TButton', 'font') or 'TkDefaultFont'
            assert tkfont.Font(root, font=strip.itemcget('status_text', 'font')).actual() == tkfont.Font(root, font=expected).actual()
    if previous_last is not None and m.last_play is None:
        seen_reclaim = True
        # 收回牌权时不清空所有玩家的历史展示数据。
        assert any(gui.player_cards)
assert seen_pass and seen_finish and seen_reclaim
assert gui.round_number == 2
assert all(gui._play_display_state(i)[0] == '等待出牌' for i in range(4))
gui.close()
print('Play area: one active wait, retained cards, PASS tiles, finish ranks and new-round reset passed')
