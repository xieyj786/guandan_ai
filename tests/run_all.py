"""无需第三方依赖的测试入口，失败返回非零退出码。"""
import runpy
import unittest
from pathlib import Path

suite = unittest.TestSuite()
for path in sorted(Path(__file__).parent.glob("test_*.py")):
    for name, test in runpy.run_path(str(path)).items():
        if name.startswith("test_") and callable(test):
            suite.addTest(unittest.FunctionTestCase(test, description=f"{path.name}: {name}"))
if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
