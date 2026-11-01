"""Standalone benchmark window: python benchmark_gui.py."""
import json
import queue
import time
import sys
from benchmark_runtime import IdleSleepGuard
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from benchmark import BenchmarkConfig, BenchmarkRun
from agents.lmstudio_client import LMStudioClient
from agents.request_metrics import measured_post
from agents.rule_agent import RuleAgent
from agents.deepseek_agent import DeepSeekAgent
from agents.llm_client import _post_json, validate_api_key, LLMRequestError


class CompatibleClient:
    """OpenAI-compatible chat endpoint; keys stay in memory, no automatic retries."""
    def __init__(self, base, model, key):
        parts=urlsplit(base)
        if parts.scheme != 'https' or not parts.netloc or parts.username or parts.query or parts.fragment:
            raise ValueError('API地址须为不含凭据及查询参数的HTTPS基础地址')
        if not model.strip(): raise ValueError('请填写模型名称')
        self.base,self.model,self.key=base.rstrip('/'),model.strip(),validate_api_key(key)

    def chat(self,prompt):
        self.last_error_kind = ''
        payload={'model':self.model,'messages':[{'role':'user','content':prompt}],
                 'stream':False,'max_tokens':512}
        if urlsplit(self.base).hostname == 'api.deepseek.com':
            payload.update(thinking={'type':'disabled'}, response_format={'type':'json_object'})
        try:
            data=measured_post(self, _post_json, self.base+'/chat/completions',
                {'Authorization':'Bearer '+self.key,'Content-Type':'application/json'},payload,timeout=25)
        except LLMRequestError as exc:
            self.last_error_kind = 'api_error'
            raise  # _post_json emits sanitized HTTP/network diagnostics.
        except Exception:
            self.last_error_kind = 'transport_error'
            raise LLMRequestError('API传输失败') from None
        try:
            choice=data['choices'][0]
            if choice.get('finish_reason')=='length':
                self.last_error_kind='truncated'
                raise LLMRequestError('模型输出达到长度上限，未作为有效决策使用')
            content=choice['message']['content']
            if not isinstance(content,str) or not content.strip():
                self.last_error_kind='empty_content'
                raise LLMRequestError('模型未返回有效正文')
            return content
        except LLMRequestError:
            raise
        except (KeyError,IndexError,TypeError):
            self.last_error_kind='invalid_response'
            raise LLMRequestError('服务返回结构不符合接口约定') from None



LOCAL_MODES = ('LM Studio', 'LM Studio（实验）')


def team_client(mode, base, model, key, timeout):
    """Local mode never validates or forwards the cloud key."""
    if mode in LOCAL_MODES:
        return LMStudioClient(model=model, base_url=base, timeout=int(timeout), speed_mode=(mode == 'LM Studio（实验）'))
    if mode == 'LLM':
        return CompatibleClient(base, model, key)
    raise ValueError('请先选择LLM或LM Studio')


from benchmark_report import duration, usage_lines, format_summary

class BenchmarkWindow:
    def __init__(self, root):
        self.root=root; root.title('掼蛋 · 独立牌局统计测试'); root.geometry('920x720')
        self.queue=queue.Queue(); self.worker=None; self.run=None; self.last_live_refresh=0.0
        self.controls=[]
        self.readonly_controls=[]
        top=ttk.Frame(root,padding=12); top.pack(fill='x')
        self.repetitions=tk.StringVar(value='50'); self.seed=tk.StringVar(value='42')
        for col,(label,var,values) in enumerate([('重复轮数',self.repetitions,('50','100','500')),('种子',self.seed,())]):
            ttk.Label(top,text=label).grid(row=0,column=col*2)
            w=ttk.Combobox(top,textvariable=var,values=values,width=9);w.grid(row=0,column=col*2+1);self.controls.append(w)
        self.plan=tk.StringVar()
        def update_plan(*_):
            try:
                count=int(self.repetitions.get())
                self.plan.set(f'{count}轮 × 13副发牌 × 换位前后2局 = {count*26}局')
            except ValueError:self.plan.set('请输入整数重复轮数')
        self.repetitions.trace_add('write',update_plan);update_plan()
        ttk.Label(top,textvariable=self.plan).grid(row=1,columnspan=6,sticky='w')
        ttk.Label(top,text='每轮级牌2至A各一局，再同牌换位；不升级、不进贡。').grid(row=2,columnspan=6,sticky='w')
        self.wild=tk.BooleanVar(value=True)
        w=ttk.Checkbutton(top,text='对局启用红心配（牌型统计始终按自然牌）',variable=self.wild)
        w.grid(row=3,columnspan=6,sticky='w');self.controls.append(w)
        self.prevent_sleep=tk.BooleanVar(value=sys.platform=='darwin')
        if sys.platform=='darwin':
            w=ttk.Checkbutton(top,text='运行期间防止Mac空闲睡眠（不保持屏幕常亮）',variable=self.prevent_sleep)
            w.grid(row=4,columnspan=6,sticky='w');self.controls.append(w)
        self.teams=[]
        self.team_refresh=[]
        for name in ('A','B'):
            box=ttk.LabelFrame(root,text=f'策略{name}：控制同队两名玩家',padding=10);box.pack(fill='x',padx=12,pady=4)
            variables=[tk.StringVar(value=v) for v in ('规则AI','https://api.deepseek.com','deepseek-flash','','180')]
            widgets=[]
            for i,(label,var) in enumerate(zip(('类型','API基础地址','模型','API Key（仅云端）','本地等待秒数'),variables)):
                ttk.Label(box,text=label).grid(row=i//2,column=(i%2)*2,sticky='w')
                w=ttk.Combobox(box,textvariable=var,values=('规则AI','LLM',*LOCAL_MODES),state='readonly',width=18) if i==0 else ttk.Entry(box,textvariable=var,width=33,show='●' if i==3 else '')
                w.grid(row=i//2,column=(i%2)*2+1,padx=5,pady=3);self.controls.append(w);widgets.append(w)
                if i==0:self.readonly_controls.append(w)
            test=ttk.Button(box,text='测试连接（云端可能计费）',command=lambda v=variables:self.test(v))
            test.grid(row=2,column=3);self.controls.append(test)
            self.teams.append(variables)
            self.setup_team_controls(variables,widgets,test)
        bar=ttk.Frame(root);bar.pack(fill='x',padx=12,pady=10)
        self.start_btn=ttk.Button(bar,text='开始并选择日志目录',command=self.start);self.start_btn.pack(side='left');self.controls.append(self.start_btn)
        ttk.Button(bar,text='暂停 / 继续',command=self.pause).pack(side='left',padx=6)
        ttk.Button(bar,text='停止',command=self.stop).pack(side='left')
        ttk.Label(root,text='每个模型队伍控制两人。LM Studio无需密钥；云端LLM可能计费，本地模型占用本机算力。').pack()
        ttk.Label(root,text='LM Studio保留原提示；“实验”省去逐次解释，可能改变模型选择，提速效果以本机日志为准。').pack()
        self.output=tk.Text(root,height=15,wrap='word');self.output.pack(fill='both',expand=True,padx=12,pady=10)
        root.protocol('WM_DELETE_WINDOW',self.close);self.poll_job=root.after(100,self.poll)

    def setup_team_controls(self, variables, widgets, test):
        # Preserve edited endpoint/model values when switching between providers.
        saved={'LLM':['https://api.deepseek.com','deepseek-flash'],
               'LM Studio':['http://127.0.0.1:1234/v1','qwen/qwen3.5-9b'],
               'LM Studio（实验）':['http://127.0.0.1:1234/v1','qwen/qwen3.5-9b']}
        previous=['规则AI']
        def refresh(*_):
            mode=variables[0].get()
            old=previous[0]
            if mode != old:
                if old in saved:saved[old]=[variables[1].get(),variables[2].get()]
                if mode in saved:
                    for var,value in zip(variables[1:3],saved[mode]):var.set(value)
                previous[0]=mode
            active=mode in saved
            for index in (1,2):widgets[index].configure(state='normal' if active else 'disabled')
            widgets[3].configure(state='normal' if mode=='LLM' else 'disabled')
            widgets[4].configure(state='normal' if mode in LOCAL_MODES else 'disabled')
            test.configure(state='normal' if active else 'disabled',
                           text='测试本地连接' if mode in LOCAL_MODES else '测试连接（云端可能计费）')
        variables[0].trace_add('write',refresh)
        self.team_refresh.append(refresh)
        refresh()

    def test(self,variables):
        try:
            mode,base,model,key,timeout=(v.get() for v in variables)
            client=team_client(mode,base,model,key,timeout)
        except Exception as e: messagebox.showerror('配置错误',str(e));return
        def work():
            try:
                if isinstance(client, LMStudioClient):client.test_connection()
                else:
                    reply=client.chat('Reply with JSON only: {"ok":true}')
                    if json.loads(reply) != {'ok':True}: raise ValueError()
                self.queue.put(('notice','连接成功；已收到符合约定的JSON回复。'))
            except Exception as exc:
                hint=('连接失败，请检查LM Studio服务、模型、等待时间及Thinking设置。'
                      if mode in LOCAL_MODES else '连接失败，请核对地址、模型、密钥和账户余额。')
                if isinstance(exc, LLMRequestError):hint += '\n具体原因：' + str(exc)
                self.queue.put(('notice',hint))
        threading.Thread(target=work,daemon=True).start()

    def start(self):
        if self.worker and self.worker.is_alive(): return
        try:
            config=BenchmarkConfig(repetitions=int(self.repetitions.get()),seed=int(self.seed.get()),wildcards=self.wild.get())
            factories=[]; labels=[]
            for variables in self.teams:
                mode,base,model,key,timeout=(v.get() for v in variables)
                if mode=='LLM' or mode in LOCAL_MODES:
                    client=team_client(mode,base,model,key,timeout)
                    factories.append(lambda name,c=client:DeepSeekAgent(name,c));labels.append(f'{mode} / {model}' if mode in LOCAL_MODES else model)
                else: factories.append(lambda name:RuleAgent(name));labels.append('规则AI')
        except Exception as e: messagebox.showerror('参数错误',str(e));return
        if any(v[0].get()=='LLM' for v in self.teams) and not messagebox.askyesno('API费用','将开始整批LLM对战并产生API费用，是否继续？'): return
        directory=filedialog.askdirectory(title='选择日志保存位置')
        if not directory:return
        folder=Path(directory)/datetime.now().strftime('benchmark-%Y%m%d-%H%M%S-%f')
        run=BenchmarkRun(config,folder,factories,labels,lambda s:self.queue.put(('summary',s)))
        self.run=run
        for w in self.controls:w.configure(state='disabled')
        self.output.delete('1.0','end');self.output.insert('end',f'日志：{folder}\n')
        prevent_sleep=self.prevent_sleep.get()
        def work():
            guard=IdleSleepGuard()
            try:
                if prevent_sleep:guard.start()
                run.run()
            except Exception as e:self.queue.put(('notice','测试停止：'+type(e).__name__+'；请检查日志目录权限。'))
            finally:
                try:guard.stop()
                finally:self.queue.put(('done',None))
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()

    def pause(self):
        if self.run:
            if self.run.play.is_set():self.run.play.clear()
            else:self.run.play.set()
    def stop(self):
        if self.run:self.run.cancel.set();self.run.play.set()
    def close(self):
        if self.worker and self.worker.is_alive():
            self.stop();messagebox.showinfo('正在停止','将在当前动作或API请求结束后停止，请稍后关闭窗口。');return
        self.root.after_cancel(self.poll_job)
        self.root.destroy()
    def poll(self):
        try:
            while True:
                kind,data=self.queue.get_nowait()
                if kind=='summary' and self.run is not None:
                    self.output.delete('1.0','end');self.output.insert('end',f'日志：{self.run.folder}\n'+(f'文本报告：{data["report_path"]}\n' if data.get('report_path') else '')+'\n'+format_summary(data))
                elif kind=='notice':messagebox.showinfo('提示',data)
                elif kind=='done':
                    for w in self.controls:w.configure(state='readonly' if w in self.readonly_controls else 'normal')
                    for refresh in self.team_refresh:refresh()

        except queue.Empty:pass
        now=time.monotonic()
        if self.worker and self.worker.is_alive() and self.run and now-self.last_live_refresh>=1:
            self.last_live_refresh=now
            self.output.delete('1.0','end')
            self.output.insert('end',f'日志：{self.run.folder}\n\n'+format_summary(self.run.summary('running')))
        self.poll_job=self.root.after(100,self.poll)


if __name__=='__main__':
    root=tk.Tk();BenchmarkWindow(root);root.mainloop()
