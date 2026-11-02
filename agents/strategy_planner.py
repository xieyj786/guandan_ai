"""兼容入口；正式实现位于 strategy/planner.py。"""
import sys
from strategy import planner as _implementation

sys.modules[__name__] = _implementation
