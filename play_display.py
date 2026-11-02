"""兼容入口；正式实现位于 presentation/play_display.py。"""
import sys
from presentation import play_display as _implementation

sys.modules[__name__] = _implementation
