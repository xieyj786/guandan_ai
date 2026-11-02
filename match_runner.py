"""兼容入口；正式实现位于 gameplay/match.py。"""
import sys
from gameplay import match as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
