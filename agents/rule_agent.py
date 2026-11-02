"""兼容入口；正式实现位于 strategy/rule_agent.py。"""
import sys
from strategy import rule_agent as _implementation

sys.modules[__name__] = _implementation
