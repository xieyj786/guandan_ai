"""Real Tk: both desktop entrypoints show the final-hand border and reset it."""
import sys
from unittest.mock import patch
import tkinter as tk
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gui import GuandanGUI
from play import GuandanPlay
from integrations.llm.settings import LLMSettings
for kind in (GuandanGUI, GuandanPlay):
    root = tk.Tk()
    root.withdraw()
    with patch.object(LLMSettings, 'load', return_value=LLMSettings()):
        app = kind(root)
    root.deiconify()
    root.update()
    card = app.match.hands[1][0]
    app.match.finish_order = [1]
    app.match.hands[1] = []
    app.match.current_player = 0
    app.player_cards[1] = [card]
    app.player_plays[1] = '最后一张'
    if isinstance(app, GuandanPlay):
        app.game.turns = 3
    else:
        app.turns = 3
    app._draw_table()
    root.update()
    expected = [(card.suit.value, int(card.rank))]
    assert app._play_display_state(1) == ('头游', [card])
    assert app.play_faces[1].cards == expected
    assert app.play_faces[1].status_text == ''
    assert app.play_faces[1].finished
    strip = app.play_faces[1]
    assert strip.find_withtag('last_hand_border')
    assert all(strip.itemcget(item, 'outline') == app.seat_labels[1].cget('fg')
               for item in strip.find_withtag('last_hand_border'))
    assert not strip.find_withtag('last_hand_text')
    strip.set_finished(False)
    before = [strip.bbox(item) for item in strip.find_withtag('card_art')]
    strip.set_finished(True, app.seat_labels[1].cget('fg'))
    after = [strip.bbox(item) for item in strip.find_withtag('card_art')]
    assert before == after, 'final-hand frame must not resize or shift card art'
    from game_engine.card import Card, Suit
    from presentation.cards import GOLD
    app.player_cards[1] = [Card(Suit.HEART, app.match.level_rank)]
    app._draw_table()
    root.update()
    assert strip.itemcget('card_highlight', 'outline') == GOLD
    assert strip.itemcget('last_hand_border', 'outline') == app.seat_labels[1].cget('fg')
    if isinstance(app, GuandanPlay):
        app.game.leading_team = 'B'
    else:
        app.leading_team = 'B'
    app._draw_table()
    root.update()
    assert strip.itemcget('last_hand_border', 'outline') == app.seat_labels[1].cget('fg')
    assert not app.play_faces[0].find_withtag('last_hand_border')
    root.lift()
    root.update()
    assert app.play_faces[1].find_all(), 'last card not drawn on actual Tk canvas'
    assert app.seat_labels[1].cget('text').splitlines() == ['B队', 'AI2', '剩余', '0', '张']
    app.new_game()
    root.update()
    assert app.play_faces[1].cards == []
    assert not app.play_faces[1].finished
    assert not app.play_faces[1].find_withtag('last_hand_border')
    app.close()
    print(kind.__name__, ': finished leader card drawn, rank retained, new round clears it', flush=True)
