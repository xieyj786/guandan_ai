"""兼容入口；正式实现位于 gameplay/contracts.py。"""
import sys
from gameplay import contracts as _implementation

sys.modules[__name__] = _implementation
