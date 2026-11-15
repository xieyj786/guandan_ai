"""在 macOS 桌面会话中运行的真实 Tk 跨局检查；创建隐藏窗口，结束后关闭。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tkinter as tk
from viewer import GuandanViewer
from gui import GuandanGUI
root=tk.Tk()
root.withdraw()
viewer=GuandanViewer(root)
steps=0
while viewer.round_number < 3 and steps < 3000 and not viewer.failed:
    viewer._advance_one()
    steps+=1
assert viewer.round_number == 3 and not viewer.failed
assert viewer.match.tribute_outcome is not None
assert viewer.match.level_rank == viewer.team_levels[viewer.leading_team]
assert all(viewer.match._build_observation(i).level_rank == viewer.match.level_rank for i in range(4))
assert '本局级牌' in viewer.level_a_status.cget('text')
assert all(len(hand)==27 for hand in viewer.match.hands)
logs=viewer.log.get('1.0', 'end')
assert '进贡' in logs and '还贡' in logs and '本局首出' in logs
print(f'viewer: {steps} steps, reached round 3, tribute logs and 27-card hands verified')
viewer.new_game()
assert viewer.round_number == 1 and viewer.match.tribute_outcome is None
viewer.close()
root=tk.Tk()
root.withdraw()
gui=GuandanGUI(root)
root.deiconify()
for geometry in ('1000x680', '1200x780'):
    root.geometry(geometry)
    root.update()
    for button in gui.control_buttons.values():
        assert button.winfo_ismapped(), button.cget("text")
        assert button.winfo_rootx() + button.winfo_width() <= root.winfo_rootx() + root.winfo_width()
    for index, row, col in ((2, 0, 1), (3, 1, 0), (1, 1, 2), (0, 2, 1)):
        label = gui.play_labels[index]
        slot = label.master
        assert int(slot.grid_info()['row']) == row and int(slot.grid_info()['column']) == col
        assert '\n' not in label.cget('text')
        assert label.cget('anchor') == ('e' if index == 1 else 'w')
    assert all(label.cget('text') == '' for label in gui.play_labels.values())
    assert gui.play_prompt.cget('text') == ''
    tiles = gui.hand_row.winfo_children()
    assert len(tiles) == 27
    columns = {}
    for tile in tiles:
        columns.setdefault(tile.rank, []).append(tile)
        assert tile.winfo_y() + tile.winfo_height() <= gui.hand_row.winfo_height()
    assert len({group[0].winfo_x() for group in columns.values()}) == len(columns)
    for group in columns.values():
        assert len({tile.winfo_x() for tile in group}) == 1
        assert len({tile.winfo_y() for tile in group}) == len(group)
    assert all(tile.winfo_x() + tile.winfo_width() <= gui.hand_row.winfo_width() for tile in tiles)
    assert gui.action_row.winfo_x() >= gui.hand_row.winfo_x() + gui.hand_row.winfo_width()
    buttons = list(gui.action_buttons.values())
    button_y = [button.winfo_rooty() for button in buttons]
    assert button_y == sorted(set(button_y))
    for button in buttons:
        assert button.winfo_ismapped()
        assert button.winfo_rooty() + button.winfo_height() <= gui.action_row.winfo_rooty() + gui.action_row.winfo_height()
    assert gui.hand_hint.winfo_rooty() > buttons[-1].winfo_rooty() + buttons[-1].winfo_height()
    assert gui.hand_hint.winfo_rooty() + gui.hand_hint.winfo_height() <= gui.action_row.winfo_rooty() + gui.action_row.winfo_height()
    record = gui.log.master
    width = root.winfo_width()
    new_button = gui.control_buttons['新局']
    top = new_button.winfo_rooty() + new_button.winfo_height()
    available = root.winfo_rooty() + root.winfo_height() - top
    assert abs(gui.center.winfo_width() - width * .65) <= 1
    assert abs(record.winfo_width() - width * .30) <= 1
    assert abs(gui.hand_panel.winfo_width() - width * .78) <= 1
    assert abs(gui.center.winfo_height() - available * .60) <= 1
    assert abs(gui.hand_panel.winfo_height() - available * .35) <= 1
    assert gui.hand_panel.winfo_rootx() == gui.center.winfo_rootx()
    assert gui.center.winfo_height() == record.winfo_height()
    assert int(gui.action_row.cget('highlightthickness')) == 0
    for button in buttons:
        assert button.winfo_width() < gui.action_row.winfo_width() * .8
    gap = available * .05 / 3
    assert abs(gui.center.winfo_rooty() - top - gap) <= 1
    assert abs(gui.hand_panel.winfo_rooty() - gui.center.winfo_rooty() - gui.center.winfo_height() - gap) <= 2
    assert abs(root.winfo_rooty() + root.winfo_height() - gui.hand_panel.winfo_rooty() - gui.hand_panel.winfo_height() - gap) <= 2
    assert gui.seats[2].winfo_y() < gui.play_area.winfo_y() < gui.seats[0].winfo_y()
    assert gui.seats[3].winfo_x() < gui.play_area.winfo_x() < gui.seats[1].winfo_x()
root.withdraw()
from turn_log import format_turn_log
from agents.rule_agent import RuleAgent
assert all(str(b.cget('state')) == 'disabled' for b in gui.action_buttons.values())
gui.start_human_game()
while gui.match.current_player != 0:
    gui._pause()
    gui._advance_one()
before = len(gui.match.hands[0])
action = RuleAgent('test').decide(gui.match._build_observation(0))
gui.selected_cards = list(action.cards)
gui._play_selected()
assert gui.turns >= 1
assert gui.player_plays[0] != '等待出牌'
assert gui.play_labels[0].cget('text') == ''
assert gui.play_prompt.cget('text') == ''
for message in format_turn_log(gui.match, 0, before, gui.turns):
    assert message in gui.log.get('1.0', 'end')
print('gui: seat positions, 27-card rank stacks, expanded columns, manual play and shared logs verified')
gui._pause()
while len(gui.match.finish_order)<4:
    gui.match._take_turn()
gui._finish_round_if_needed()
assert gui.round_number==2 and gui.match.tribute_outcome is not None
if gui.match.tribute_pending:
    gui.selected_cards = [gui.match.tribute_session.eligible_cards()[0]]
    gui._submit_exchange(gui.match.tribute_session.pending[0])
assert all(len(hand)==27 for hand in gui.match.hands)
print('gui: reached round 2 with tribute applied')
gui.close()
