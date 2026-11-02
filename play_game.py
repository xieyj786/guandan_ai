"""兼容入口；正式实现位于 gameplay/offline.py。"""
import sys
from gameplay import offline as _implementation

sys.modules[__name__] = _implementation
