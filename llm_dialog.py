"""DeepSeek 本机配置窗口。密钥只在用户点击读取或保存时访问钥匙串。"""
from __future__ import annotations
import json
import tkinter as tk
from tkinter import ttk
from agents.llm_client import DeepSeekLLMClient, LLMRequestError, validate_api_key
from llm_settings import LLMSettings, Keychain, KeychainError, background, credential_store_name


class LLMDialog:
    def __init__(self, parent, settings, on_saved, keychain=None, on_close=None):
        self.parent = parent
        self.saving = False
        self.on_saved = on_saved
        self.on_close = on_close
        self.keychain = keychain
        self.window = tk.Toplevel(parent)
        self.window.title('LLM 设置 · DeepSeek · 跨平台版 1.4')
        self.window.geometry('560x420')
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.bind('<Escape>', lambda event: self.close())
        self.closed = False
        self.poll_id = None
        self.busy = False
        self.secret = tk.StringVar()
        self.model = tk.StringVar(value=settings.model)
        self.seat = tk.StringVar(value=f'AI{settings.seat + 1}')
        self.enabled = tk.BooleanVar(value=settings.enabled)
        body = ttk.Frame(self.window, padding=20)
        body.pack(fill='both', expand=True)
        body.columnconfigure(1, weight=1)
        for row, label in enumerate(('服务商', 'API Key', '模型', 'LLM 玩家')):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=10)
        ttk.Label(body, text='DeepSeek · https://api.deepseek.com').grid(row=0, column=1, sticky='w')
        ttk.Entry(body, textvariable=self.secret, show='●').grid(row=1, column=1, sticky='ew')
        ttk.Combobox(body, textvariable=self.model, values=('deepseek-flash', 'deepseek-v4-pro')).grid(row=2, column=1, sticky='ew')
        ttk.Combobox(body, textvariable=self.seat, values=('AI1', 'AI2', 'AI3', 'AI4'), state='readonly').grid(row=3, column=1, sticky='ew')
        ttk.Label(body, text='保存连接配置后，在主界面打开“接入 LLM”开关。').grid(row=4, columnspan=2, sticky='w', pady=8)
        ttk.Label(body, text=f'人机模式下 AI1 始终由你操作；可选 AI2～AI4 使用模型。\n密钥保存在{credential_store_name()}。连接测试和对局调用会产生 API 费用。',
                  wraplength=510).grid(row=5, columnspan=2, sticky='w', pady=8)
        buttons = ttk.Frame(body)
        buttons.grid(row=6, columnspan=2, sticky='w', pady=8)
        self.buttons = []
        for label, callback in [('读取已存密钥', self.load_key), ('测试连接', self.test), ('保存设置', self.save)]:
            button = ttk.Button(buttons, text=label, command=callback)
            button.pack(side='left', padx=3)
            self.buttons.append(button)
        self.close_button = ttk.Button(buttons, text='关闭', command=self.close)
        self.close_button.pack(side='left', padx=3)
        self.message = ttk.Label(body, text='粘贴新密钥，或读取已保存的密钥。', wraplength=510)
        self.message.grid(row=7, columnspan=2, sticky='w', pady=8)

    def store(self):
        if self.keychain is None:
            self.keychain = Keychain()
        return self.keychain

    def _run(self, work, done):
        if self.busy:
            return
        self.busy = True
        for button in self.buttons:
            button.configure(state='disabled')
        future = background(work)
        def poll():
            self.poll_id = None
            if self.closed and not self.saving:
                return
            if not future.done():
                self.poll_id = self.parent.after(80, poll)
                return
            self.busy = False
            if not self.closed:
                for button in self.buttons:
                    button.configure(state='normal')
            try:
                done(future.result())
            except (KeychainError, LLMRequestError) as exc:
                if not self.closed:
                    self.message.configure(text=str(exc))
            except Exception:
                if not self.closed:
                    self.message.configure(text='操作失败，请检查本机保存权限、网络或模型设置。')
            finally:
                self.saving = False
        self.poll_id = self.parent.after(80, poll)

    def load_key(self):
        self.message.configure(text=f'正在读取{credential_store_name()}；系统可能请求允许访问。')
        def done(value):
            self.secret.set(value)
            self.message.configure(text='已读取密钥。' if value else '尚未保存密钥，请粘贴。')
        self._run(lambda: self.store().get(), done)

    def test(self):
        secret, model = self.secret.get().strip(), self.model.get().strip()
        if not secret or not model:
            self.message.configure(text='请先填写密钥和模型。')
            return
        self.message.configure(text='正在测试真实连接…')
        def work():
            client = DeepSeekLLMClient(secret, model=model, max_retries=1)
            data = json.loads(client.chat('连接测试。请只输出 JSON：{"ok":true}'))
            if not isinstance(data, dict) or data.get('ok') is not True:
                raise LLMRequestError('服务已响应，但测试回答格式不符合要求')
        self._run(work, lambda _: self.message.configure(text='连接成功：已收到 DeepSeek 的真实响应。可以保存设置。'))

    def save(self):
        if self.busy or self.closed:
            return
        secret, model = self.secret.get().strip(), self.model.get().strip()
        settings = LLMSettings(self.enabled.get(), model, int(self.seat.get()[2:]) - 1)
        if not model:
            self.message.configure(text='请填写模型名称。')
            return
        def work():
            if secret:
                self.store().set(validate_api_key(secret))
            elif settings.enabled:
                validate_api_key(self.store().get())
            settings.save()
        def done(_):
            self.on_saved(settings)
            self.close()
        self.saving = True
        self.message.configure(text="正在保存设置…保存成功后自动返回牌桌。")
        self._run(work, done)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.poll_id and not self.saving:
            self.parent.after_cancel(self.poll_id)
            self.poll_id = None
        self.secret.set('')
        self.window.destroy()
        if self.on_close:
            self.on_close()
