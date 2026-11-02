"""真实 Tk，假网络/钥匙串：验证后台响应、过期丢弃、配置窗口。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import threading
import time
from unittest.mock import patch
import tkinter as tk
from agents.deepseek_agent import DeepSeekAgent
from llm_settings import LLMSettings
from llm_dialog import LLMDialog
from viewer import GuandanViewer


def pump(root, condition, timeout=5):
    start = time.monotonic()
    while not condition():
        root.update()
        if time.monotonic() - start > timeout:
            raise AssertionError('UI timeout')
        time.sleep(.01)
    root.update()


class Slow:
    def __init__(self):
        self.ready = threading.Event()
        self.calls = 0
    def chat(self, prompt):
        self.calls += 1
        self.ready.wait(4)
        return '{"action_id":0,"reason":"测试选择"}'


root = tk.Tk()
root.withdraw()
with patch.object(LLMSettings, 'load', return_value=LLMSettings()):
    gui = GuandanViewer(root)

# 即使磁盘保存启用，启动仍默认关闭；切换不重发牌。
assert not gui.llm_enabled.get()
original_hands = [list(h) for h in gui.match.hands]
gui.llm_settings = LLMSettings(True, 'deepseek-flash', 1)
gui.llm_enabled.set(True)
gui._toggle_llm()
assert isinstance(gui.match.agents[1], DeepSeekAgent)
gui.llm_enabled.set(False)
gui._toggle_llm()
assert all(not isinstance(a, DeepSeekAgent) for a in gui.match.agents)
assert gui.match.hands == original_hands

# 单步异步执行，UI可继续响应；重复单步不会重复请求。
index = gui.match.current_player
client = Slow()
gui.match.agents[index] = DeepSeekAgent(f'AI{index+1}', client)
before = [list(h) for h in gui.match.hands]
gui.single_step()
assert gui.pending_job and gui.turns == 0
for _ in range(3):
    gui.single_step()
assert client.calls == 1
client.ready.set()
pump(root, lambda: gui.pending_job is None)
assert gui.turns == 1 and not gui.running
assert gui.match.hands != before
assert 'DeepSeek' in gui.log.get('1.0', 'end')

# 非法模型回答会落到规则策略，仍正常推进。
class Invalid:
    def chat(self, prompt): return '{"action_id":999999}'
index = gui.match.current_player
gui.match.agents[index] = DeepSeekAgent(f'AI{index+1}', Invalid())
turns = gui.turns
gui.single_step()
pump(root, lambda: gui.pending_job is None)
assert gui.turns == turns + 1 and not gui.failed
assert '规则接管' in gui.log.get('1.0', 'end')

# 重开后旧回答被丢弃。
index = gui.match.current_player
client = Slow()
gui.match.agents[index] = DeepSeekAgent(f'AI{index+1}', client)
gui.single_step()
old = gui.match
gui.new_game()
current = gui.match
before = [list(h) for h in current.hands]
client.ready.set()
pump(root, lambda: gui.network_future.done())
assert gui.match is current and current is not old
assert current.hands == before and gui.turns == 0

# 自动播放在等待模型时可暂停，不接受过期结果。
index = gui.match.current_player
client = Slow()
gui.match.agents[index] = DeepSeekAgent(f'AI{index+1}', client)
gui.toggle_auto()
assert gui.pending_job and gui.running
gui.toggle_auto()
client.ready.set()
pump(root, lambda: gui.network_future.done())
assert not gui.running and gui.turns == 0

# 设置座位跨新局及升级后的下一局保留。
gui.llm_settings = LLMSettings(True, 'test-model', 2, 'LM Studio')
gui.llm_enabled.set(True)
gui._toggle_llm()
gui.new_game()
assert isinstance(gui.match.agents[2], DeepSeekAgent)
assert gui.match.agents[2].client.provider_name == 'LM Studio'
gui._start_round(42)
assert isinstance(gui.match.agents[2], DeepSeekAgent)
# 配置窗口复用，关闭时销毁。
gui.open_llm_settings()
dialog = gui.llm_dialog
gui.open_llm_settings()
assert gui.llm_dialog is dialog and not dialog.closed
gui.close()
assert dialog.closed
print('Viewer LLM: async step, fallback, reset, pause, seat, local provider and settings passed')
