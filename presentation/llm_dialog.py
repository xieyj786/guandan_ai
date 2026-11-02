"""DeepSeek / LM Studio 本机配置窗口。密钥只在用户点击读取或保存时访问钥匙串。"""
from __future__ import annotations
import json
import tkinter as tk
from tkinter import ttk
from integrations.llm.client import DeepSeekLLMClient, LLMRequestError, validate_api_key
from integrations.llm.settings import LLMSettings, Keychain, KeychainError, background, credential_store_name, configured_local_client


class LLMDialog:
    def __init__(self, parent, settings, on_saved, keychain=None, on_close=None):
        self.parent = parent
        self.saving = False
        self.on_saved = on_saved
        self.on_close = on_close
        self.keychain = keychain
        self.window = tk.Toplevel(parent)
        self.window.title('LLM 设置 · DeepSeek / LM Studio')
        self.window.geometry('680x650')
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.bind('<Escape>', lambda event: self.close())
        self.closed = False
        self.poll_id = None
        self.busy = False
        self.provider = tk.StringVar(value=settings.provider)
        self.base_url = tk.StringVar(value=settings.base_url)
        self.timeout = tk.StringVar(value=str(settings.local_timeout))
        self.compact = tk.BooleanVar(value=settings.local_speed_mode)
        self._previous_provider = settings.provider
        self._models = {'DeepSeek': 'deepseek-flash', 'LM Studio': 'qwen/qwen3.5-9b'}
        self._models[settings.provider] = settings.model
        self.secret = tk.StringVar()
        self.model = tk.StringVar(value=settings.model)
        self.seat = tk.StringVar(value=f'AI{settings.seat + 1}')
        self.enabled = tk.BooleanVar(value=settings.enabled)
        body = ttk.Frame(self.window, padding=20)
        body.pack(fill='both', expand=True)
        body.columnconfigure(1, weight=1)
        labels = ('服务商', 'API Key（仅DeepSeek）', '模型标识', 'LLM 玩家',
                  '本地API地址', '本地等待秒数')
        for row, label in enumerate(labels):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=8)
        provider = ttk.Combobox(body, textvariable=self.provider,
                               values=('DeepSeek', 'LM Studio'), state='readonly')
        provider.grid(row=0, column=1, sticky='ew')
        provider.bind('<<ComboboxSelected>>', self._provider_changed)
        self.secret_entry = ttk.Entry(body, textvariable=self.secret, show='●')
        self.secret_entry.grid(row=1, column=1, sticky='ew')
        self.model_entry = ttk.Combobox(body, textvariable=self.model)
        self.model_entry.grid(row=2, column=1, sticky='ew')
        ttk.Combobox(body, textvariable=self.seat, values=('AI1', 'AI2', 'AI3', 'AI4'),
                     state='readonly').grid(row=3, column=1, sticky='ew')
        self.url_entry = ttk.Entry(body, textvariable=self.base_url)
        self.url_entry.grid(row=4, column=1, sticky='ew')
        self.timeout_entry = ttk.Entry(body, textvariable=self.timeout)
        self.timeout_entry.grid(row=5, column=1, sticky='ew')
        ttk.Label(body, text='保存后打开主界面的“接入 LLM”。人机模式请选择AI2～AI4。',
                  wraplength=590).grid(row=6, columnspan=2, sticky='w', pady=8)
        self.provider_hint = ttk.Label(body, wraplength=590)
        self.provider_hint.grid(row=7, columnspan=2, sticky='w', pady=8)
        buttons = ttk.Frame(body)
        buttons.grid(row=8, columnspan=2, sticky='w', pady=8)
        self.buttons = []
        for label, callback in [('读取已存密钥', self.load_key), ('测试连接', self.test), ('保存设置', self.save)]:
            button = ttk.Button(buttons, text=label, command=callback)
            button.pack(side='left', padx=3)
            self.buttons.append(button)
        self.close_button = ttk.Button(buttons, text='关闭', command=self.close)
        self.close_button.pack(side='left', padx=3)
        self.message = ttk.Label(body, text='粘贴新密钥，或读取已保存的密钥。', wraplength=510)
        self.message.grid(row=9, columnspan=2, sticky='w', pady=8)
        self.compact_control = ttk.Checkbutton(body, text='本地精简模式（实验）：保留全部动作，仅返回编号，不生成解释', variable=self.compact)
        self.compact_control.grid(row=10, columnspan=2, sticky='w', pady=6)
        self._provider_changed()

    def _provider_changed(self, event=None):
        provider = self.provider.get()
        if provider != self._previous_provider:
            self._models[self._previous_provider] = self.model.get()
            self.model.set(self._models[provider])
            self._previous_provider = provider
        local = provider == 'LM Studio'
        self.compact_control.configure(state='normal' if local else 'disabled')
        self.secret_entry.configure(state='disabled' if local else 'normal')
        self.url_entry.configure(state='normal' if local else 'disabled')
        self.timeout_entry.configure(state='normal' if local else 'disabled')
        self.model_entry.configure(values=('qwen/qwen3.5-9b',) if local else
                                   ('deepseek-flash', 'deepseek-v4-pro'))
        self.provider_hint.configure(text=(
            'LM Studio须在本机启动服务。本地模式不读DeepSeek密钥、不收云端Token费。'
            '当前支持未启用认证的本机服务；不支持局域网地址。' if local else
            f'DeepSeek密钥保存在{credential_store_name()}；测试和对局调用可能计费。'))
        self.message.configure(text='LM Studio无需填写API Key；先测试连接，再保存。' if local else
                               '粘贴DeepSeek新密钥，或读取已保存的密钥。')

    def _settings(self):
        provider = self.provider.get()
        model = self.model.get().strip()
        if provider not in ('DeepSeek', 'LM Studio') or not model:
            raise ValueError('请选择服务商并填写模型标识')
        settings = LLMSettings(self.enabled.get(), model, int(self.seat.get()[2:]) - 1,
                               provider, self.base_url.get().strip(),
                               int(self.timeout.get()) if provider == 'LM Studio' else 180,
                               self.compact.get() if provider == 'LM Studio' else False)
        if provider == 'LM Studio':
            configured_local_client(settings)  # Validate before starting a worker.
        return settings

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
        if self.provider.get() == 'LM Studio':
            self.message.configure(text='本地模式无需读取DeepSeek密钥。')
            return
        self.message.configure(text=f'正在读取{credential_store_name()}；系统可能请求允许访问。')
        def done(value):
            self.secret.set(value)
            self.message.configure(text='已读取密钥。' if value else '尚未保存密钥，请粘贴。')
        self._run(lambda: self.store().get(), done)

    def test(self):
        if self.busy or self.closed:
            return
        try:
            settings = self._settings()
            secret = self.secret.get().strip()
            if settings.provider == 'DeepSeek':
                secret = validate_api_key(secret)
        except (ValueError, LLMRequestError) as exc:
            self.message.configure(text=str(exc))
            return
        self.message.configure(text='正在测试真实连接…本地模型首次响应可能较慢。')
        def work():
            if settings.provider == 'LM Studio':
                configured_local_client(settings).test_connection()
            else:
                client = DeepSeekLLMClient(secret, model=settings.model, max_retries=1)
                data = json.loads(client.chat('连接测试。请只输出 JSON：{"ok":true}'))
                if not isinstance(data, dict) or data.get('ok') is not True:
                    raise LLMRequestError('服务已响应，但测试回答格式不符合要求')
        self._run(work, lambda _: self.message.configure(
            text=f'连接成功：{settings.provider} 已返回符合约定的JSON。可以保存设置。'))

    def save(self):
        if self.busy or self.closed:
            return
        try:
            settings = self._settings()
        except ValueError as exc:
            self.message.configure(text=str(exc))
            return
        secret = self.secret.get().strip()
        def work():
            if settings.provider == 'DeepSeek':
                if secret:
                    self.store().set(validate_api_key(secret))
                elif settings.enabled:
                    validate_api_key(self.store().get())
            settings.save()
        def done(_):
            self.on_saved(settings)
            self.close()
        self.saving = True
        self.message.configure(text='正在保存设置…保存成功后自动返回牌桌。')
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
