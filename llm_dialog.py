"""兼容入口；正式实现位于 presentation/llm_dialog.py。"""
import sys
from presentation import llm_dialog as _implementation

sys.modules[__name__] = _implementation
