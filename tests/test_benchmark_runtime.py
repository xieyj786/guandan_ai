from unittest.mock import patch,Mock
from benchmark_runtime import IdleSleepGuard


def test_sleep_guard_lifetime_and_non_mac_boundary():
    process=Mock()
    with patch('benchmark_runtime.sys.platform','darwin'),patch('benchmark_runtime.subprocess.Popen',return_value=process) as launch:
        guard=IdleSleepGuard();guard.start()
        args=launch.call_args.args[0]
        assert args[:3]==['/usr/bin/caffeinate','-i','-w']
        guard.stop();guard.stop()
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=2)
    with patch('benchmark_runtime.sys.platform','win32'),patch('benchmark_runtime.subprocess.Popen') as launch:
        guard=IdleSleepGuard();guard.start();guard.stop();launch.assert_not_called()
