"""兼容入口；正式实现位于 gameplay/turn_log.py。"""
import sys
from gameplay import turn_log as _implementation

sys.modules[__name__] = _implementation
