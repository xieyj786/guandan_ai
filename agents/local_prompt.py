"""兼容入口；正式实现位于 integrations/llm/local_prompt.py。"""
import sys
from integrations.llm import local_prompt as _implementation

sys.modules[__name__] = _implementation
