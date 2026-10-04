"""在非Windows主机模拟 Win32 边界；不声称替代实机测试。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ctypes as C
from unittest.mock import Mock, patch
import llm_settings as module


def test_platform_store_and_settings_location():
    with patch.object(module.sys, 'platform', 'win32'), patch.dict(module.os.environ, {'LOCALAPPDATA':'/tmp/windows-local'}), patch.object(module, 'WindowsCredentials') as backend:
        assert module.settings_path() == Path('/tmp/windows-local/guandan_ai/llm.json')
        store = module.Keychain()
        store.set('example')
        backend.return_value.set.assert_called_once_with('example')
        store.get()
        backend.return_value.get.assert_called_once()
    with patch.object(module.sys, 'platform', 'darwin'), patch.object(module, 'MacKeychain') as backend:
        module.Keychain().get()
        backend.return_value.get.assert_called_once()


def test_windows_native_boundary_roundtrip_and_errors():
    lib = Mock()
    saved = {}
    def write(ptr, flags):
        entry = C.cast(ptr, C.POINTER(module.Credential)).contents
        assert entry.Type == 1 and entry.Persist == 2
        assert entry.TargetName == 'guandan_ai.deepseek'
        saved['data'] = C.string_at(entry.CredentialBlob, entry.CredentialBlobSize)
        return 1
    def read(target, kind, flags, output):
        blob = (C.c_ubyte * len(saved['data'])).from_buffer_copy(saved['data'])
        entry = module.Credential()
        entry.CredentialBlob = C.cast(blob, C.POINTER(C.c_ubyte))
        entry.CredentialBlobSize = len(blob)
        saved['keepalive'] = (entry, blob)
        C.cast(output, C.POINTER(C.POINTER(module.Credential)))[0] = C.pointer(entry)
        return 1
    lib.CredWriteW.side_effect = write
    lib.CredReadW.side_effect = read
    with patch.object(C, 'WinDLL', return_value=lib, create=True):
        store = module.WindowsCredentials()
    store.set('dummy-test-key')
    assert store.get() == 'dummy-test-key'
    store.set('replacement')
    assert store.get() == 'replacement'
    assert lib.CredFree.call_count == 2
    lib.CredReadW.side_effect = None
    lib.CredReadW.return_value = 0
    with patch.object(C, 'get_last_error', return_value=1168, create=True):
        assert store.get() == ''
    with patch.object(C, 'get_last_error', return_value=5, create=True):
        try:
            store.get()
            assert False
        except module.KeychainError as exc:
            assert '5' in str(exc)
        lib.CredWriteW.side_effect = None
        lib.CredWriteW.return_value = 0
        try:
            store.set('private-test-value')
            assert False
        except module.KeychainError as exc:
            assert 'private-test-value' not in str(exc)
