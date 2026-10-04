"""
LLM 客户端封装。

迁移自此前 Coze 生成的 llm_coze.py / llm_deepseek.py，重构要点：
    1. 把两个厂商重复的"重试 + 429退避"逻辑提到 BaseLLMClient，子类只需实现
       _send_request()，只处理厂商特定的请求体/响应体格式。
    2. chat() 请求失败时抛出 LLMRequestError，而不是静默返回空字符串。
       这一点很关键：此前 agent_player.py 的 _call_llm() 永远返回 ""，
       调用方（Agent）无法区分"LLM说了空话"和"LLM请求根本没打出去"，
       导致 LLM 实际上从未被真正调用、也从未被发现。显式抛异常后，
       LLMAgent 才能正确地区分"调用失败走fallback"和"正常解析"。
"""

from __future__ import annotations

import time
import json
import ssl
import socket
import sys
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMRequestError(Exception):
    """LLM 请求在重试耗尽后仍然失败。"""


def validate_api_key(key: str) -> str:
    key = key.strip()
    if not key:
        raise LLMRequestError('请填写完整 API Key')
    if any(c in key for c in '*•●…') or '...' in key:
        raise LLMRequestError('密钥含遮掩符号，无法用于认证。请复制创建时显示的完整 API Key；若无法查看，请在平台新建密钥。')
    if not key.isascii() or any(c.isspace() for c in key):
        raise LLMRequestError('密钥含空白或非英文字符，请重新复制完整 API Key')
    return key


def _tls_context() -> ssl.SSLContext:
    """保留证书和主机名验证；补充 macOS 系统 CA，兼容缺少 CA 的 Homebrew Python。"""
    context = ssl.create_default_context()
    system_ca = Path('/etc/ssl/cert.pem')
    if sys.platform == 'darwin' and system_ca.is_file():
        context.load_verify_locations(cafile=str(system_ca))
    return context


def _connection_error(exc: Exception) -> str:
    reason = exc.reason if isinstance(exc, URLError) else exc
    if isinstance(reason, ssl.SSLCertVerificationError):
        return 'HTTPS证书验证失败，请检查本机可信证书或代理证书设置'
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return '连接或读取响应超时，请稍后重试'
    if isinstance(reason, socket.gaierror):
        return '无法解析服务地址，请检查网络或DNS设置'
    if isinstance(reason, ssl.SSLError):
        return 'HTTPS安全连接失败，请检查网络或代理设置'
    return '无法连接服务，请检查网络、代理或防火墙设置'


def _post_json(url: str, headers: dict[str, str], payload: dict, timeout: float = 60) -> dict:
    """使用标准库发送 JSON 请求，避免把可选的 LLM 功能变成运行时依赖。"""
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout, context=_tls_context()) as response:  # noqa: S310 - URL 由调用方显式配置
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429:
            raise LLMRequestError("429 限流") from exc
        messages = {401: "密钥无效，请检查 API Key", 402: "账户余额不足", 403: "服务拒绝访问", 400: "请求参数或模型名称不正确"}
        raise LLMRequestError(messages.get(exc.code, f"服务请求失败：HTTP {exc.code}")) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise LLMRequestError('服务返回的内容不是有效JSON，请稍后重试') from exc
    except (URLError, OSError) as exc:
        raise LLMRequestError(_connection_error(exc)) from exc


class BaseLLMClient(ABC):
    """所有 LLM 客户端的公共基类：统一 chat() 入口 + 指数退避重试。"""

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def chat(self, prompt: str) -> str:
        """
        发送 prompt，返回纯文本回复。
        失败（网络异常 / 429 / 空响应）按指数退避重试，重试耗尽后抛出 LLMRequestError。
        """
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                result = self._send_request(prompt)
                if result:
                    return result
                last_error = LLMRequestError("LLM 返回了空响应")
            except LLMRequestError as exc:
                last_error = exc
            except Exception:
                last_error = LLMRequestError("服务响应格式异常")

            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (2 ** attempt))

        raise LLMRequestError(f"LLM 请求失败，已尝试 {self.max_retries} 次：{last_error}")

    @abstractmethod
    def _send_request(self, prompt: str) -> str:
        """向具体厂商发送请求，返回文本回复。子类实现，异常直接抛出，由 chat() 统一处理重试。"""
        raise NotImplementedError


class CozeLLMClient(BaseLLMClient):
    """
    Coze（扣子）Bot API 客户端。
    使用方法：
        1. https://www.coze.cn/open 申请 Personal Access Token
        2. 创建一个 Bot，获取 Bot ID
        3. CozeLLMClient(bot_id=..., token=...)
    """

    def __init__(self, bot_id: str, token: str, base_url: str = "https://api.coze.cn", **kwargs):
        super().__init__(**kwargs)
        self.bot_id = bot_id
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _send_request(self, prompt: str) -> str:
        url = f"{self.base_url}/v3/chat"
        payload = {
            "bot_id": self.bot_id,
            "user_id": "guandan_player",
            "stream": False,
            "auto_save_history": True,
            "messages": [{"role": "user", "content": prompt, "content_type": "text"}],
        }
        data = _post_json(url, self.headers, payload)
        messages = (data.get("data") or {}).get("messages") or []
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("type") == "answer":
                return msg.get("content", "")
        return ""


class DeepSeekLLMClient(BaseLLMClient):
    """
    DeepSeek API 客户端。
    使用 JSON 输出和非思考模式；测试通过注入假客户端完成，不伪装真实连接成功。
    """

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com", model: str = "deepseek-flash", timeout: float = 25, **kwargs):
        super().__init__(**kwargs)
        api_key = validate_api_key(api_key)
        self.timeout = timeout
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def _send_request(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "stream": False,
                   "thinking": {"type": "disabled"}, "response_format": {"type": "json_object"},
                   "max_tokens": 256}
        data = _post_json(url, self.headers, payload, timeout=self.timeout)
        choices = data.get("choices") or []
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""
