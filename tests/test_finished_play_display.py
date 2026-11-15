"""Finished players must keep their last cards in both desktop renderers."""
from types import SimpleNamespace
from game_engine.card import Card, Rank, Suit
from presentation.gui import GuandanGUI
from presentation.play import GuandanPlay


class DisplaySink:
    def __init__(self):
        self.cards = None
        self.status = None
        self.finished = False

    def set_finished(self, finished, color=None):
        self.finished = finished
        self.finished_color = color if finished else None

    def configure(self, **kwargs):
        pass

    def set_cards(self, cards, level):
        self.cards, self.status = cards, None

    def set_status(self, status):
        self.cards, self.status = [], status


def display_state(gui_type, finish_order):
    card = Card(Suit.SPADE, Rank.ACE)
    state = SimpleNamespace(
        match=SimpleNamespace(finish_order=finish_order, current_player=0,
                              hands=[[card], [], [card], [card]], level_rank=Rank.TWO),
        turns=3, player_cards=[[], [card], [], []],
        player_plays=['等待出牌', 'A', '过牌', '过牌'],
        seats=dict.fromkeys(range(4)), series_finished=False,
        play_prompt=DisplaySink(),
        seat_labels={i: DisplaySink() for i in range(4)},
        play_labels={i: DisplaySink() for i in range(4)},
        play_faces={i: DisplaySink() for i in range(4)},
        _pending_exchange_kind=lambda: None, _team_color=lambda team: 'gold',
        _draw_hand=lambda: None,
    )
    state._play_display_state = lambda index: gui_type._play_display_state(state, index)
    return state, card


def test_finished_leaders_last_card_reaches_both_desktop_renderers():
    for gui_type in (GuandanGUI, GuandanPlay):
        state, card = display_state(gui_type, [1])
        assert state._play_display_state(1) == ('头游', [card])
        assert state._play_display_state(0) == ('等待出牌', [])
        assert state._play_display_state(2) == ('PASS', [])
        gui_type._draw_table(state)
        assert state.play_faces[1].cards == [('spade', 14)]
        assert state.play_faces[1].status is None
        assert state.play_faces[1].finished
        assert state.play_faces[1].finished_color == 'gold'
        assert not state.play_faces[2].finished
        assert state.play_faces[2].status == 'PASS'


def test_all_finish_places_keep_cards_until_new_round_reset():
    for gui_type in (GuandanGUI, GuandanPlay):
        state, card = display_state(gui_type, [1, 3, 0, 2])
        state.player_cards = [[card] for _ in range(4)]
        for index, place in zip(state.match.finish_order, ('头游', '二游', '三游', '末游')):
            assert state._play_display_state(index) == (place, [card])
        state.match.current_player = 3  # Partner takes the next lead.
        assert state._play_display_state(1) == ('头游', [card])
        state.turns = 0
        state.match.finish_order = []
        state.player_cards = [[] for _ in range(4)]
        assert all(state._play_display_state(i) == ('等待出牌', []) for i in range(4))
