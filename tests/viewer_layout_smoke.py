"""Viewer control alignment, sidebar width and half-card overlap in real Tk."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tkinter as tk
from tkinter import ttk
from presentation.viewer import GuandanViewer
from gameplay.randomness import NORMAL, REPLAY

root = tk.Tk()
gui = GuandanViewer(root)
for size in ('1000x740', '1180x820', '1500x1000'):
    root.geometry(size)
    for mode in (NORMAL, REPLAY):
        controls = gui.random_controls
        controls.mode.set(mode); controls.refresh()
        root.update()
        selector = next(w for w in controls.row.winfo_children() if isinstance(w, ttk.Combobox))
        llm = next(w for w in controls.row.master.winfo_children() if isinstance(w, ttk.Button))
        assert abs(selector.winfo_rootx() + selector.winfo_width() - root.winfo_rootx() - root.winfo_width() + 14) <= 2
        assert abs(llm.winfo_rooty() + llm.winfo_height()/2 - selector.winfo_rooty() - selector.winfo_height()/2) <= 3
        assert controls.row.winfo_rootx() >= llm.winfo_rootx() + llm.winfo_width()
        sidebar = gui.play_faces.master.master
        assert sidebar.winfo_width() == 319
        panels = [panel for panel, _, _ in gui.panels.values()]
        assert len({panel.winfo_width() for panel in panels}) == 1
        for _, _, area in gui.panels.values():
            cards = area.winfo_children()
            assert len(cards) == 27
            for a, b in zip(cards, cards[1:]):
                assert abs(b.winfo_x() - a.winfo_x() - a.winfo_width()/2) <= 1
            assert cards[-1].winfo_x() + cards[-1].winfo_width() <= area.winfo_width() + 1
            assert max(c.winfo_y() + c.winfo_height() for c in cards) <= area.winfo_height()
    print(size, 'viewer alignment, 319 sidebar and 50% overlap OK', flush=True)
gui.close()
