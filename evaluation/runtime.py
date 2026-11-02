"""Prevent macOS idle sleep for the lifetime of an active LLM workload."""
import os
import subprocess
import sys


class IdleSleepGuard:
    def __init__(self):
        self.process = None

    def start(self):
        if sys.platform != 'darwin':
            return
        # -i prevents idle system sleep without keeping the display on.
        # -w also releases the assertion if the GUI process exits unexpectedly.
        self.process = subprocess.Popen(['/usr/bin/caffeinate', '-i', '-w', str(os.getpid())],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop(self):
        if self.process is not None:
            process, self.process = self.process, None
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
