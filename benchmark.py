"""兼容入口；正式实现位于 evaluation/benchmark.py。"""
import sys
from evaluation import benchmark as _implementation

sys.modules[__name__] = _implementation
