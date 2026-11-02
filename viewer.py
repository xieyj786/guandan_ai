"""兼容入口；正式实现位于 presentation/viewer.py。"""
import sys
from presentation import viewer as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
