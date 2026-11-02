"""兼容入口；正式实现位于 integrations/llm/activity.py。"""
import sys
from integrations.llm import activity as _implementation

sys.modules[__name__] = _implementation
