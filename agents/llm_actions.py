"""兼容入口；正式实现位于 integrations/llm/actions.py。"""
import sys
from integrations.llm import actions as _implementation

sys.modules[__name__] = _implementation
