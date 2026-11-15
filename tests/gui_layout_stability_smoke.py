"""Verify that gameplay never changes the table geometry at a fixed window size."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tkinter as tk
from unittest.mock import patch
from presentation.gui import GuandanGUI
from presentation.play import GuandanPlay
from integrations.llm.settings import LLMSettings

root = tk.Tk()
with patch.object(LLMSettings, 'load', return_value=LLMSettings()):
    gui = (GuandanPlay if '--play' in sys.argv else GuandanGUI)(root)
widgets = [gui.table, *gui.seats.values(), gui.center, gui.play_area,
           gui.log.master, gui.hand_row, gui.action_row]
def bounds():
    return [(w.winfo_x(), w.winfo_y(), w.winfo_width(), w.winfo_height()) for w in widgets]
labels = dict(gui.seat_labels)
buttons = dict(gui.action_buttons)
for geometry in ('1000x680', '1200x850'):
    root.geometry(geometry)
    root.update()
    expected = bounds()
    card_widths = [strip.target_card_width for strip in gui.play_faces.values()]
    for _ in range(240):
        gui.single_step()
        root.update()
        assert [strip.target_card_width for strip in gui.play_faces.values()] == card_widths
        assert bounds() == expected, (geometry, gui.turns, expected, bounds())
        assert gui.seat_labels == labels and gui.action_buttons == buttons
        for seat in (1, 3):
            text = gui.seat_labels[seat].cget('text')
            assert len(text.splitlines()) == 5
    assert not gui.failed
assert gui.round_number >= 2
# The offline entry uses the same uncluttered table and toolbar-sized PASS.
assert all(label.cget('text') == '' for label in gui.play_labels.values())
assert all(strip.cget('bg') == gui.play_area.cget('bg') for strip in gui.play_faces.values())
assert all(tile.winfo_y() + tile.winfo_height() <= gui.hand_row.winfo_height()
           for tile in gui.hand_tiles)
for seat, alignment in {3: 'right', 1: 'left', 0: 'top', 2: 'bottom'}.items():
    strip = gui.play_faces[seat]
    assert strip.alignment == alignment
    strip.set_status('PASS')
    root.update()
    button = gui.control_buttons['新局']
    x1, y1, x2, y2 = strip.coords('status_box')
    from tkinter import font as tkfont
    from tkinter import ttk
    font = ttk.Style(strip).lookup(button.cget('style') or 'TButton', 'font') or 'TkDefaultFont'
    assert abs(x2-x1+1-tkfont.Font(root=strip, font=font).measure('MMMMM')) < .01
    assert abs(y2-y1+1-button.winfo_height()) < .01
    assert strip.status_button is button
assert gui.play_prompt.cget('text') == ''

# Mode changes also reuse the same frame and action widgets.
gui.start_human_game()
root.update()
assert bounds() == expected
assert gui.action_buttons == buttons
gui.close()
print('Fixed sidebar widths and unchanged frame geometry verified over 480 turns and mode changes')
