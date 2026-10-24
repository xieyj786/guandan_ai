"""Standalone benchmark window: python benchmark_gui.py."""
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from benchmark import BenchmarkConfig, BenchmarkRun
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
            data=_post_json(self.base+'/chat/completions',
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



def format_summary(data):
    rate=lambda v: '暂无' if v is None else f'{v:.2%}'
    names={'running':'运行中','completed':'已结束','cancelled':'已停止'}
    lines=[f"状态：{names.get(data['status'],data['status'])}  完成：{data['completed']}/{data['planned']}  失败：{data['failed']}",
           f"策略A（{data['labels'][0]}）：{data['wins_A']}胜，胜率{rate(data['win_rate_A'])}",
           f"策略B（{data['labels'][1]}）：{data['wins_B']}胜，胜率{rate(data['win_rate_B'])}",
           f"LLM决策：{data['llm_decisions']}；规则回退：{data['fallback_decisions']}次；含回退完成局：{data['fallback_rounds']}",
           f"累计耗时：{data['elapsed_seconds']:.1f}秒（含暂停）",'自然牌型（总次数 / 每局平均）：']
    for key,label in [('straight_flush','同花顺窗口'),('bomb6','6张炸弹'),('bomb7','7张炸弹'),('bomb8','8张炸弹'),('joker_bomb','王炸')]:
        avg=data['average_per_round'][key]
        lines.append(f"  {label}：{data['patterns'][key]} / {avg:.4f}" if avg is not None else f"  {label}：暂无")
    interval=data['independent_wilson95_A']
    if interval:lines.append(f"A胜率95%区间：{rate(interval[0])}～{rate(interval[1])}")
    else:lines.append('配对模式或无完成局：不报告独立样本置信区间')
    lines.append('回退分类：'+json.dumps(data.get('fallback_reasons',{}),ensure_ascii=False))
    if data.get('fallback_decisions',0):lines.append('注意：存在规则接管，以上不是纯LLM胜率。')
    return '\n'.join(lines)

class BenchmarkWindow:
    def __init__(self, root):
        self.root=root; root.title('掼蛋 · 独立牌局统计测试'); root.geometry('920x720')
        self.queue=queue.Queue(); self.worker=None; self.run=None
        self.controls=[]
        self.readonly_controls=[]
        top=ttk.Frame(root,padding=12); top.pack(fill='x')
        self.rounds=tk.StringVar(value='250'); self.seed=tk.StringVar(value='42'); self.level=tk.StringVar(value='2')
        for col,(label,var,values) in enumerate([('局数',self.rounds,('250','500','1000')),('种子',self.seed,()),('级牌（A=14）',self.level,tuple(map(str,range(2,15))))]):
            ttk.Label(top,text=label).grid(row=0,column=col*2)
            w=ttk.Combobox(top,textvariable=var,values=values,width=9);w.grid(row=0,column=col*2+1);self.controls.append(w)
        self.paired=tk.BooleanVar(); self.wild=tk.BooleanVar(value=True)
        for text,var in [('同牌换位配对（偶数局，非完全独立）',self.paired),('对局启用红心配（牌型统计始终按自然牌）',self.wild)]:
            w=ttk.Checkbutton(top,text=text,variable=var);w.grid(columnspan=6,sticky='w');self.controls.append(w)
        self.teams=[]
        for name in ('A','B'):
            box=ttk.LabelFrame(root,text=f'策略{name}：控制同队两名玩家',padding=10);box.pack(fill='x',padx=12,pady=4)
            variables=[tk.StringVar(value=v) for v in ('规则AI','https://api.deepseek.com','deepseek-flash','')]
            for i,(label,var) in enumerate(zip(('类型','API基础地址','模型','API Key（不保存）'),variables)):
                ttk.Label(box,text=label).grid(row=i//2,column=(i%2)*2,sticky='w')
                w=ttk.Combobox(box,textvariable=var,values=('规则AI','LLM'),state='readonly',width=18) if i==0 else ttk.Entry(box,textvariable=var,width=33,show='●' if i==3 else '')
                w.grid(row=i//2,column=(i%2)*2+1,padx=5,pady=3);self.controls.append(w)
                if i==0:self.readonly_controls.append(w)
            test=ttk.Button(box,text='测试连接（可能计费）',command=lambda v=variables:self.test(v));test.grid(row=2,column=1);self.controls.append(test)
            self.teams.append(variables)
        bar=ttk.Frame(root);bar.pack(fill='x',padx=12,pady=10)
        self.start_btn=ttk.Button(bar,text='开始并选择日志目录',command=self.start);self.start_btn.pack(side='left');self.controls.append(self.start_btn)
        ttk.Button(bar,text='暂停 / 继续',command=self.pause).pack(side='left',padx=6)
        ttk.Button(bar,text='停止',command=self.stop).pack(side='left')
        ttk.Label(root,text='密钥只在内存中。每个LLM队伍控制两人；整批测试可能产生大量API请求。').pack()
        self.output=tk.Text(root,height=15,wrap='word');self.output.pack(fill='both',expand=True,padx=12,pady=10)
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(100,self.poll)

    def test(self,variables):
        try: client=CompatibleClient(*(v.get() for v in variables[1:]))
        except Exception as e: messagebox.showerror('配置错误',str(e));return
        def work():
            try:
                reply=client.chat('Reply with JSON only: {"ok":true}')
                if json.loads(reply) != {'ok':True}: raise ValueError()
                self.queue.put(('notice','连接成功；已收到符合约定的JSON回复。'))
            except Exception: self.queue.put(('notice','连接失败，请核对地址、模型、密钥和账户余额。'))
        threading.Thread(target=work,daemon=True).start()

    def start(self):
        if self.worker and self.worker.is_alive(): return
        try:
            config=BenchmarkConfig(int(self.rounds.get()),int(self.seed.get()),int(self.level.get()),self.paired.get(),self.wild.get())
            factories=[]; labels=[]
            for variables in self.teams:
                mode,base,model,key=(v.get() for v in variables)
                if mode=='LLM':
                    client=CompatibleClient(base,model,key)
                    factories.append(lambda name,c=client:DeepSeekAgent(name,c));labels.append(model)
                else: factories.append(lambda name:RuleAgent(name));labels.append('规则AI')
        except Exception as e: messagebox.showerror('参数错误',str(e));return
        if any(v[0].get()=='LLM' for v in self.teams) and not messagebox.askyesno('API费用','将开始整批LLM对战并产生API费用，是否继续？'): return
        directory=filedialog.askdirectory(title='选择日志保存位置')
        if not directory:return
        folder=Path(directory)/datetime.now().strftime('benchmark-%Y%m%d-%H%M%S-%f')
        self.run=BenchmarkRun(config,folder,factories,labels,lambda s:self.queue.put(('summary',s)))
        for w in self.controls:w.configure(state='disabled')
        self.output.delete('1.0','end');self.output.insert('end',f'日志：{folder}\n')
        def work():
            try:self.run.run()
            except Exception as e:self.queue.put(('notice','测试停止：'+type(e).__name__+'；请检查日志目录权限。'))
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
        self.root.destroy()
    def poll(self):
        try:
            while True:
                kind,data=self.queue.get_nowait()
                if kind=='summary':
                    self.output.delete('1.0','end');self.output.insert('end',f'日志：{self.run.folder}\n\n'+format_summary(data))
                elif kind=='notice':messagebox.showinfo('提示',data)
                elif kind=='done':
                    for w in self.controls:w.configure(state='readonly' if w in self.readonly_controls else 'normal')

        except queue.Empty:pass
        self.root.after(100,self.poll)


if __name__=='__main__':
    root=tk.Tk();BenchmarkWindow(root);root.mainloop()
