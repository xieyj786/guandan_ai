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
    assert sum(status == '等待出牌' for status, _ in states) == 1
    assert states[m.current_player][0] == '等待出牌'
    for i in range(4):
        if i != actor:
            assert gui.player_cards[i] == previous_cards[i]
        if i in m.finish_order:
            seen_finish = True
            assert states[i][0] == ('头游','二游','三游','末游')[m.finish_order.index(i)]
            assert not states[i][1]
        if states[i][0] == 'PASS':
            seen_pass = True
            strip = gui.play_faces[i]
            assert strip.status_text == 'PASS' and not strip.cards
            texts = [strip.itemcget(item, 'text') for item in strip.find_all() if strip.type(item) == 'text']
            assert texts == ['PASS']
    if previous_last is not None and m.last_play is None:
        seen_reclaim = True
        # 收回牌权时不清空所有玩家的历史展示数据。
        assert any(gui.player_cards)
assert seen_pass and seen_finish and seen_reclaim
assert gui.round_number == 2
assert all(gui._play_display_state(i)[0] == '等待出牌' for i in range(4))
gui.close()
print('Play area: one active wait, retained cards, PASS tiles, finish ranks and new-round reset passed')
