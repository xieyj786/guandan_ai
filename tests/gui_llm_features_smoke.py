"""Native Tk; fake network. Verify shared optimizations and discarded-result accounting."""
import sys,time,threading
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import tkinter as tk
from gui import GuandanGUI
from llm_settings import LLMSettings,configured_client
from llm_dialog import LLMDialog
from agents.deepseek_agent import DeepSeekAgent
from agents.lmstudio_client import LMStudioClient
from game_engine.card import Card,Rank,Suit


def pump(root,condition,timeout=8):
    deadline=time.monotonic()+timeout
    while not condition():
        root.update();time.sleep(.01)
        assert time.monotonic()<deadline,'UI timeout'
    root.update()

root=tk.Tk()
with patch.object(LLMSettings,'load',return_value=LLMSettings()):app=GuandanGUI(root)
root.update()
assert app.llm_stats_label.winfo_ismapped()
assert app.llm_stats_label.winfo_y()<app.table.winfo_y()
reply={'choices':[{'finish_reason':'stop','message':{'content':'{"action_id":0}'}}],
       'usage':{'prompt_tokens':10,'completion_tokens':4,'total_tokens':14}}
index=app.match.current_player
app.match.agents[index]=DeepSeekAgent(f'AI{index+1}',LMStudioClient(speed_mode=True))
with patch('agents.lmstudio_client._post_json',return_value=reply):
    app.single_step();pump(root,lambda:app.pending_job is None)
    pump(root,lambda:'请求1次' in app.llm_stats_label.cget('text'))
    assert not app.failed and '输入10' in app.llm_stats_label.cget('text')

class Never:
    def chat(self,prompt):raise AssertionError('forced move must not request model')
index=app.match.current_player
app.match.last_play=None;app.match.hands[index]=[Card(Suit.SPADE,Rank.THREE)]
app.match.agents[index]=DeepSeekAgent(f'AI{index+1}',Never())
app.single_step();pump(root,lambda:app.pending_job is None)
s=app.llm_activity.summary()
assert s['automatic']==1 and s['usage']['requests']==1 and s['fallbacks']==0

# Reset while a real adapter is waiting for a mocked HTTP response.
release=threading.Event();entered=threading.Event()
index=app.match.current_player
app.match.agents[index]=DeepSeekAgent(f'AI{index+1}',LMStudioClient(speed_mode=True))
def slow(*args,**kwargs):entered.set();release.wait(5);return reply
with patch('agents.lmstudio_client._post_json',side_effect=slow):
    app.single_step();pump(root,entered.is_set)
    if sys.platform=='darwin':pump(root,lambda:app.sleep_guard.process is not None)
    app.new_game();current=app.match;hands=[list(h) for h in current.hands]
    release.set();pump(root,lambda:app.network_future.done())
    pump(root,lambda:'请求2次' in app.llm_stats_label.cget('text'))
    assert app.match is current and app.match.hands==hands and app.turns==0
    assert app.llm_activity.summary()['usage']['total_tokens']==28
    pump(root,lambda:app.sleep_guard.process is None)

# The opt-in setting uses the exact client tested by the benchmark.
dialog=LLMDialog(root,LLMSettings(provider='LM Studio',model='qwen/qwen3.5-9b'),lambda _:None)
dialog.compact.set(True)
assert configured_client(dialog._settings()).speed_mode is True
dialog.provider.set('DeepSeek');dialog._provider_changed()
assert str(dialog.compact_control['state'])=='disabled'
assert not dialog._settings().local_speed_mode
dialog.provider.set('LM Studio');dialog._provider_changed()
assert dialog._settings().local_speed_mode
dialog.close();app.close()
print('GUI LLM features: native controls, local opt-in, usage, forced-move skip and stale-response accounting passed')
