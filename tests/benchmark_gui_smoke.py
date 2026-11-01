import sys,time,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import tkinter as tk
import benchmark_gui as module
with tempfile.TemporaryDirectory() as folder:
    module.filedialog.askdirectory=lambda **kw:folder
    notices=[]
    module.messagebox.showinfo=lambda *a:notices.append(a)
    module.messagebox.showerror=lambda *a:notices.append(a)
    root=tk.Tk(); app=module.BenchmarkWindow(root)
    app.repetitions.set('1');app.start();app.pause()
    for _ in range(10):root.update();time.sleep(.03)
    assert not app.run.play.is_set()
    app.pause()
    deadline=time.monotonic()+180
    while app.worker.is_alive() and time.monotonic()<deadline:root.update();time.sleep(.02)
    for _ in range(10):root.update();time.sleep(.03)
    assert not app.worker.is_alive()
    assert app.run.summary('completed')['completed']==26
    assert '胜率' in app.output.get('1.0','end')
    report=Path(app.run.report_path)
    assert report.name=='benchmark_log_001.txt' and report.exists()
    assert 'benchmark_gui.py' in report.read_text()
    assert str(report) in app.output.get('1.0','end')
    assert str(app.start_btn['state'])=='normal'
    root.destroy()
    assert not notices,notices
print('Benchmark GUI: 26 real rounds, pause/resume, summary and control reset passed')

# Test local controls, JSON connection schema, agent wiring and state restoration
# with simulated inference; never sends a paid or local model request.
from unittest.mock import patch
import json
with tempfile.TemporaryDirectory() as folder:
    module.filedialog.askdirectory=lambda **kw:folder
    root=tk.Tk();app=module.BenchmarkWindow(root)
    team=app.teams[0]
    team[0].set('LM Studio');root.update()
    assert team[1].get()=='http://127.0.0.1:1234/v1'
    assert team[2].get()=='qwen/qwen3.5-9b'
    team[2].set('custom-local-model');team[0].set('LLM');team[0].set('LM Studio')
    assert team[2].get()=='custom-local-model'
    team[3].set('must-not-send');team[4].set('240')
    seen=[]
    def reply(url,headers,payload,timeout):
        seen.append((url,headers,payload,timeout))
        required=payload['response_format']['json_schema']['schema']['required']
        content={'ok':True} if required==['ok'] else {'action_id':0,'reason':'test'}
        return {'choices':[{'message':{'content':json.dumps(content)}}],
                'usage':{'prompt_tokens':10,'completion_tokens':4,'total_tokens':14}}
    with patch('agents.lmstudio_client._post_json',side_effect=reply),patch.object(
            module.messagebox,'askyesno',side_effect=AssertionError('local cloud-fee prompt')):
        app.test(team)
        deadline=time.monotonic()+5
        while not seen and time.monotonic()<deadline:root.update();time.sleep(.01)
        assert seen and seen[0][2]['response_format']['json_schema']['schema']['required']==['ok']
        app.repetitions.set('1');app.start()
        deadline=time.monotonic()+60
        while app.worker.is_alive() and time.monotonic()<deadline:root.update();time.sleep(.02)
        for _ in range(10):root.update();time.sleep(.03)
        assert not app.worker.is_alive()
        result=app.run.summary('completed')
        assert result['completed']==26 and result['llm_decisions']>0
        assert result['fallback_decisions']==0
        assert result['automatic_actions']>0
        assert result['automatic_actions_by_strategy']['A']==result['automatic_actions']
        assert result['llm_decisions']==result['usage']['requests']
        assert result['usage']['requests']==len(seen)-1
        assert result['usage']['total_tokens']==14*(len(seen)-1)
        assert 'Token' in app.output.get('1.0','end')
        assert '钟表总时长' in app.output.get('1.0','end')
        assert result['labels'][0]=='LM Studio / custom-local-model'
        assert all(headers=={'Content-Type':'application/json'} and timeout==240
                   for _,headers,_,timeout in seen)
        local_entries=[w for w in app.controls if isinstance(w,module.ttk.Entry)
                       and str(w.cget('textvariable'))==str(team[3])]
        assert str(local_entries[0]['state'])=='disabled'
        assert 'must-not-send' not in ''.join(p.read_text(encoding='utf-8-sig')
                   for p in app.run.folder.iterdir())
    root.destroy()
print('Benchmark LM Studio GUI: defaults, provider switch, mock connection and 26 rounds passed')
