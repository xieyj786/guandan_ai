"""真实 Tk 检查正常/测试切换、种子输入验证与下一局配置冻结。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tkinter as tk
from unittest.mock import patch
from presentation.gui import GuandanGUI
from presentation.viewer import GuandanViewer
from gameplay.randomness import NORMAL, REPLAY

for app in (GuandanGUI, GuandanViewer):
    root = tk.Tk(); root.withdraw()
    with patch("gameplay.randomness.secrets.randbits", side_effect=[500, 700]):
        gui = app(root)
        c = gui.random_controls
        assert gui.randomness.mode == NORMAL and gui.match.seed == 500
        assert not c.entry.winfo_manager()
        c.mode.set(REPLAY); c.seed.set("42"); c.refresh()
        gui.new_game()
        first = gui.match.hands
        assert gui.match.seed == 42 and c.entry.winfo_manager() == "pack"
        # Pending invalid settings do not affect the next round of the active series.
        c.seed.set("invalid"); c.mode.set(NORMAL)
        gui._start_round()
        assert gui.match.seed == 43
        c.mode.set(REPLAY)
        match = gui.match
        gui.new_game()
        assert gui.match is match
        c.seed.set("42"); gui.new_game()
        assert gui.match.hands == first
        c.mode.set(NORMAL); c.seed.set("invalid"); c.refresh()
        gui.new_game()
        assert gui.match.seed == 700 and not c.entry.winfo_manager()
        assert len(gui.round_records) == 1
    gui.close()
print("PASS: GUI/viewer normal/replay switch, hidden/invalid seed, frozen series, repeated seed")
