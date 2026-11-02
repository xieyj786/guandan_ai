"""兼容入口；正式实现位于 integrations/llm/metrics.py。"""
import sys
from integrations.llm import metrics as _implementation

sys.modules[__name__] = _implementation
