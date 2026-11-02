"""兼容入口；正式实现位于 integrations/llm/client.py。"""
import sys
from integrations.llm import client as _implementation

sys.modules[__name__] = _implementation
