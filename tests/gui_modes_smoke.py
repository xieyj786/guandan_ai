"""真实 Tk 模式回归：观察模式与 viewer 同步、人机操作完整升级到A。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tkinter as tk
from gui import GuandanGUI
from viewer import GuandanViewer
from agents.rule_agent import RuleAgent

root = tk.Tk(); root.withdraw()
gui = GuandanGUI(root)
other = tk.Tk(); other.withdraw()
viewer = GuandanViewer(other)
gui.seed = 41
gui.new_game()
assert not gui.human_mode
for _ in range(250):
    gui.single_step()
    viewer.single_step()
    assert gui.round_number == viewer.round_number
    assert gui.match.hands == viewer.match.hands
    assert gui.match.current_player == viewer.match.current_player
    assert not gui.running and gui.after_id is None
    assert all(str(button.cget('state')) == 'disabled' for button in gui.action_buttons.values())
assert not gui.failed
# 播放中按单步只暂停；旧回调取消，新局不继承自动播放。
gui.toggle_auto()
assert gui.running and gui.after_id is not None
turns = gui.turns
gui.single_step()
assert not gui.running and gui.after_id is None and gui.turns == turns
gui.toggle_auto(); gui.new_game()
assert gui.after_id is None and not gui.running
viewer.close()
print('observer matches viewer for 250 actions; pause/reset timers verified', flush=True)

# 使用规则代理提供测试选择，仍通过人工按钮入口执行；生产代码不替人出牌。
gui.seed = 100  # 固定覆盖新策略下的进贡和还贡
gui.start_human_game()
assert gui.human_mode
assert gui.match.current_player == gui.match.opening_deal.first_player
assert str(gui.control_buttons['自动播放'].cget('state')) == 'disabled'
assert len(gui.action_buttons) == 4
counts = {'play': 0, 'pass': 0, 'tribute': 0, 'return': 0}
for step in range(20000):
    if gui.series_finished:
        break
    assert not gui.failed
    if gui.match.tribute_pending:
        kind = gui.match.tribute_session.pending[0]
        assert not gui.running
        gui.selected_cards = [gui.match.tribute_session.eligible_cards()[0]]
        gui._submit_exchange(kind)
        counts[kind] += 1
    elif gui.match.current_player == 0 and not gui.match._is_finished(0):
        assert not gui.running
        action = RuleAgent('test').decide(gui.match._build_observation(0))
        gui.selected_cards = list(action.cards)
        if action.action_type == 'play':
            gui._play_selected()
        else:
            gui._pass_human()
        counts[action.action_type] += 1
    else:
        # 加速执行已排队的定时动作，保持原有 step 调度路径。
        assert gui.running and gui.after_id is not None
        root.after_cancel(gui.after_id)
        gui.step()
else:
    raise AssertionError('人机模式未在20000步内完成比赛')
assert gui.series_finished and not gui.running and gui.after_id is None
assert all(counts[k] > 0 for k in counts), counts
assert max(gui.team_levels.values()).name == 'ACE'
print(f'human mode completed {gui.round_number} rounds: {counts}', flush=True)
gui.close()
