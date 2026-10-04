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
from gui import GuandanGUI


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
    gui = GuandanGUI(root)

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

# 保存的座位设置在新局应用；人机模式不会覆盖AI1。
gui.llm_enabled.set(True)
gui.llm_settings = LLMSettings(True, 'deepseek-flash', 0)
gui.start_human_game()
assert not isinstance(gui.match.agents[0], DeepSeekAgent)
gui.llm_settings = LLMSettings(True, 'deepseek-flash', 1)
gui.new_game()
assert isinstance(gui.match.agents[1], DeepSeekAgent)
gui.llm_enabled.set(False)
gui.llm_settings = LLMSettings()
gui.new_game()

class Store:
    value = 'dummy-test-key'
    def get(self): return self.value
    def set(self, key): self.value = key

saved = []
store = Store()
dialog = LLMDialog(root, LLMSettings(), saved.append, keychain=store)
dialog.load_key()
pump(root, lambda: not dialog.busy)
assert dialog.secret.get() == store.value
with patch('llm_dialog.DeepSeekLLMClient.chat', return_value='{"ok":true}'):
    dialog.test()
    pump(root, lambda: not dialog.busy)
assert '连接成功' in dialog.message.cget('text')
dialog.enabled.set(True)
with patch.object(LLMSettings, 'save') as save:
    dialog.save()
    pump(root, lambda: not dialog.busy)
    assert save.called
assert saved[0].enabled and dialog.secret.get() == ''
assert dialog.closed and not dialog.window.winfo_exists()
dialog.close()
# 保存期间仍可关闭；完成后设置回调只执行一次，不访问已销毁窗口。
release = threading.Event()
late_saved = []
late = LLMDialog(root, LLMSettings(), late_saved.append, keychain=store)
assert not late.window.transient()
late.secret.set('dummy-test-key')
with patch.object(LLMSettings, 'save', side_effect=lambda: release.wait(3)):
    late.save()
    assert late.busy and str(late.close_button.cget('state')) == 'normal'
    late.close_button.invoke()
    assert late.closed and not late.window.winfo_exists()
    release.set()
    pump(root, lambda: not late.busy)
assert len(late_saved) == 1
late.close()  # 重复关闭安全

# 关闭时有请求，后台线程不再访问Tk。
index = gui.match.current_player
client = Slow()
gui.match.agents[index] = DeepSeekAgent('AI', client)
gui.single_step()
gui.close()
client.ready.set()
print('LLM GUI: async single-step, reset, pause, seat selection, settings and close passed')
