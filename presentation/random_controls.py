"""新游戏生效的随机模式选项；不改变正在运行的牌局。"""
import tkinter as tk
from tkinter import ttk
from gameplay.randomness import MODES, NORMAL, REPLAY, SeedSequence


class RandomControls:
    def __init__(self, parent):
        self.mode = tk.StringVar(value=NORMAL)
        self.seed = tk.StringVar(value="42")
        self.row = row = ttk.Frame(parent)
        row.pack(fill="x", padx=14, pady=4)
        combo = ttk.Combobox(row, textvariable=self.mode, values=MODES, state="readonly", width=14)
        combo.pack(side="left")
        self.label = ttk.Label(row, text="种子")
        self.entry = ttk.Entry(row, textvariable=self.seed, width=24)
        self.hint = ttk.Label(row, text="模式与种子在新游戏时生效")
        self.hint.pack(side="right")
        combo.bind("<<ComboboxSelected>>", lambda _: self.refresh())
        self.refresh()

    def refresh(self):
        if self.mode.get() == REPLAY:
            self.label.pack(side="left", padx=5)
            self.entry.pack(side="left")
        else:
            self.label.pack_forget()
            self.entry.pack_forget()

    def selection(self):
        return SeedSequence(int(self.seed.get()) if self.mode.get() == REPLAY else None)
