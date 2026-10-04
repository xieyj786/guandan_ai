"""跨平台本机设置、系统凭据存储和不访问 Tk 的后台任务。"""
from __future__ import annotations

import ctypes as C
import json
import os
import sys
import threading
from concurrent.futures import Future
from dataclasses import dataclass, asdict
from pathlib import Path

def settings_path():
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData/Local') / 'guandan_ai/llm.json'
    return Path.home() / 'Library/Application Support/guandan_ai/llm.json'


SETTINGS_PATH = settings_path()
SERVICE = b'guandan_ai.deepseek'
ACCOUNT = b'api_key'


class KeychainError(Exception):
    pass


class MacKeychain:
    """直接调用系统 API，密钥不会出现在命令行参数或文件中。"""
    def __init__(self):
        if sys.platform != 'darwin':
            raise KeychainError('钥匙串保存仅支持 macOS')
        self.lib = C.CDLL('/System/Library/Frameworks/Security.framework/Security')
        self.cf = C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        self.cf.CFRelease.argtypes = [C.c_void_p]
        self.cf.CFRelease.restype = None
        self.lib.SecKeychainFindGenericPassword.argtypes = [C.c_void_p, C.c_uint32, C.c_char_p,
            C.c_uint32, C.c_char_p, C.POINTER(C.c_uint32), C.POINTER(C.c_void_p), C.POINTER(C.c_void_p)]
        self.lib.SecKeychainFindGenericPassword.restype = C.c_int32
        self.lib.SecKeychainItemFreeContent.argtypes = [C.c_void_p, C.c_void_p]
        self.lib.SecKeychainItemFreeContent.restype = C.c_int32
        self.lib.SecKeychainAddGenericPassword.argtypes = [C.c_void_p, C.c_uint32, C.c_char_p,
            C.c_uint32, C.c_char_p, C.c_uint32, C.c_char_p, C.c_void_p]
        self.lib.SecKeychainAddGenericPassword.restype = C.c_int32
        self.lib.SecKeychainItemModifyAttributesAndData.argtypes = [C.c_void_p, C.c_void_p, C.c_uint32, C.c_char_p]
        self.lib.SecKeychainItemModifyAttributesAndData.restype = C.c_int32

    def _find(self):
        length, data, item = C.c_uint32(), C.c_void_p(), C.c_void_p()
        status = self.lib.SecKeychainFindGenericPassword(None, len(SERVICE), SERVICE,
            len(ACCOUNT), ACCOUNT, C.byref(length), C.byref(data), C.byref(item))
        if status not in (0, -25300):
            raise KeychainError(f'无法访问钥匙串（{status}），请解锁或允许访问')
        return status, length, data, item

    def get(self) -> str:
        status, length, data, item = self._find()
        if status == -25300:
            return ''
        try:
            return C.string_at(data, length.value).decode('utf-8')
        finally:
            self.lib.SecKeychainItemFreeContent(None, data)
            if item:
                self.cf.CFRelease(item)

    def set(self, secret: str) -> None:
        encoded = secret.encode('utf-8')
        status, _, data, item = self._find()
        try:
            if status == -25300:
                result = self.lib.SecKeychainAddGenericPassword(None, len(SERVICE), SERVICE,
                    len(ACCOUNT), ACCOUNT, len(encoded), encoded, None)
            else:
                result = self.lib.SecKeychainItemModifyAttributesAndData(item, None, len(encoded), encoded)
            if result:
                raise KeychainError(f'钥匙串保存失败（{result}），未写入明文文件')
        finally:
            if data:
                self.lib.SecKeychainItemFreeContent(None, data)
            if item:
                self.cf.CFRelease(item)


class Credential(C.Structure):
    # 固定32位字段，避免非Windows测试机的 c_ulong 宽度不同。
    _fields_ = [('Flags', C.c_uint32), ('Type', C.c_uint32),
                ('TargetName', C.c_wchar_p), ('Comment', C.c_wchar_p),
                ('LastWritten', C.c_uint32 * 2), ('CredentialBlobSize', C.c_uint32),
                ('CredentialBlob', C.POINTER(C.c_ubyte)), ('Persist', C.c_uint32),
                ('AttributeCount', C.c_uint32), ('Attributes', C.c_void_p),
                ('TargetAlias', C.c_wchar_p), ('UserName', C.c_wchar_p)]


class WindowsCredentials:
    def __init__(self):
        # Windows 专有 ctypes API，避免在其他平台导入时访问。
        self.lib = getattr(C, 'WinDLL')('Advapi32.dll', use_last_error=True)
        self.last_error = lambda: getattr(C, 'get_last_error')()
        self.lib.CredReadW.argtypes = [C.c_wchar_p, C.c_uint32, C.c_uint32,
                                      C.POINTER(C.POINTER(Credential))]
        self.lib.CredReadW.restype = C.c_int32
        self.lib.CredWriteW.argtypes = [C.POINTER(Credential), C.c_uint32]
        self.lib.CredWriteW.restype = C.c_int32
        self.lib.CredFree.argtypes = [C.c_void_p]
        self.lib.CredFree.restype = None

    def get(self):
        entry = C.POINTER(Credential)()
        if not self.lib.CredReadW(SERVICE.decode(), 1, 0, C.byref(entry)):
            code = self.last_error()
            if code == 1168:  # ERROR_NOT_FOUND
                return ''
            raise KeychainError(f'无法读取 Windows 凭据管理器（{code}）')
        try:
            return C.string_at(entry.contents.CredentialBlob,
                               entry.contents.CredentialBlobSize).decode('utf-8')
        finally:
            self.lib.CredFree(entry)

    def set(self, secret):
        data = secret.encode('utf-8')
        if len(data) > 2560:
            raise KeychainError('密钥长度超过 Windows 凭据管理器限制')
        blob = (C.c_ubyte * len(data)).from_buffer_copy(data)
        entry = Credential()
        entry.Type = 1  # CRED_TYPE_GENERIC
        entry.TargetName = SERVICE.decode()
        entry.UserName = ACCOUNT.decode()
        entry.Persist = 2  # 同一计算机、同一用户，跨登录保留
        entry.CredentialBlobSize = len(data)
        entry.CredentialBlob = C.cast(blob, C.POINTER(C.c_ubyte))
        if not self.lib.CredWriteW(C.byref(entry), 0):
            raise KeychainError(f'Windows 凭据保存失败（{self.last_error()}），未写入明文文件')


def credential_store_name():
    return 'Windows 凭据管理器' if sys.platform == 'win32' else 'macOS 钥匙串'


class Keychain:
    """兼容已有调用入口，自动选择平台凭据存储。"""
    def __init__(self):
        if sys.platform == 'win32':
            self.backend = WindowsCredentials()
        elif sys.platform == 'darwin':
            self.backend = MacKeychain()
        else:
            raise KeychainError('当前支持 Windows 和 macOS 的系统密钥存储')

    def get(self):
        return self.backend.get()

    def set(self, secret):
        self.backend.set(secret)


@dataclass
class LLMSettings:
    enabled: bool = False
    model: str = 'deepseek-flash'
    seat: int = 0

    @classmethod
    def load(cls, path: Path = SETTINGS_PATH) -> 'LLMSettings':
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if (not isinstance(data, dict) or type(data.get('enabled')) is not bool
                    or type(data.get('seat')) is not int or not 0 <= data['seat'] < 4
                    or not isinstance(data.get('model'), str) or not data['model'].strip()):
                return cls()
            return cls(data['enabled'], data['model'].strip(), data['seat'])
        except (OSError, ValueError):
            return cls()

    def save(self, path: Path = SETTINGS_PATH):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)


def background(work) -> Future:
    """守护线程不阻止退出；结果由 Tk 主线程轮询，后台不修改牌局。"""
    future = Future()
    def run():
        try:
            future.set_result(work())
        except Exception as exc:
            future.set_exception(exc)
    threading.Thread(target=run, daemon=True).start()
    return future


class StoredDeepSeekClient:
    """仅在后台首次请求时读取系统凭据，不在启动 GUI 时请求密钥。"""
    def __init__(self, model: str):
        self.model = model
        self.client = None

    def chat(self, prompt: str) -> str:
        from agents.llm_client import DeepSeekLLMClient, LLMRequestError
        if self.client is None:
            try:
                key = Keychain().get()
            except KeychainError as exc:
                raise LLMRequestError(str(exc)) from exc
            if not key:
                raise LLMRequestError('未保存 API Key，请打开 LLM 设置')
            self.client = DeepSeekLLMClient(key, model=self.model, max_retries=1)
        return self.client.chat(prompt)
