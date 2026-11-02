"""兼容入口；正式实现位于 evaluation/runtime.py。"""
import sys
from evaluation import runtime as _implementation

sys.modules[__name__] = _implementation
