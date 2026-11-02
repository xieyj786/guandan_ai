"""兼容入口；正式实现位于 integrations/llm/legacy_agent.py。"""
import sys
from integrations.llm import legacy_agent as _implementation

sys.modules[__name__] = _implementation
