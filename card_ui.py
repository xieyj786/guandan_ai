"""兼容入口；正式实现位于 presentation/cards.py。"""
import sys
from presentation import cards as _implementation

sys.modules[__name__] = _implementation
