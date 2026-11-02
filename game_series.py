"""兼容入口；正式实现位于 gameplay/series.py。"""
import sys
from gameplay import series as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
