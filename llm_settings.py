"""兼容入口；正式实现位于 integrations/llm/settings.py。"""
import sys
from integrations.llm import settings as _implementation

sys.modules[__name__] = _implementation
