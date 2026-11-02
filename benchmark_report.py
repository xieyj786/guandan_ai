"""兼容入口；正式实现位于 evaluation/report.py。"""
import sys
from evaluation import report as _implementation

sys.modules[__name__] = _implementation
