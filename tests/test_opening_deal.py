import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collections import Counter
from unittest.mock import patch
from game_engine.card import Card, Rank, Suit
from game_engine.deck import build_deck, deal_opening, opening_count


def test_opening_counts_and_unique_deck():
    for rank, count in ((Rank.ACE,1),(Rank.NINE,9),(Rank.JACK,11),(Rank.QUEEN,12),(Rank.KING,13)):
        assert opening_count(Card(Suit.DIAMOND,rank)) == count
    for seed in range(40):
        d = deal_opening(seed)
        assert list(map(len,d.hands)) == [27]*4
        assert Counter(c for h in d.hands for c in h) == Counter(build_deck())
        assert sorted(i for h in d.card_ids for i in h) == list(range(108))
        assert d.face_up_id in d.card_ids[d.first_player]
        assert d.hands[d.first_player][d.card_ids[d.first_player].index(d.face_up_id)] == d.face_up_card
        assert d.face_up_card.suit != Suit.JOKER
        assert d == deal_opening(seed)


def test_diamond_nine_at_sixth_card_is_received_by_ai2():
    deck=build_deck()
    chosen=next(i for i,c in enumerate(deck) if c==Card(Suit.DIAMOND,Rank.NINE))
    joker=next(i for i,c in enumerate(deck) if c.suit==Suit.JOKER)
    with patch('game_engine.deck.random.Random') as factory:
        rng=factory.return_value
        rng.randrange.side_effect=[joker,chosen,5]
        d=deal_opening(42)
    assert d.first_receiver==0 and d.first_player==1
    assert d.face_up_position==5 and d.face_up_id==chosen
    assert d.card_ids[1][1]==chosen
    # 另一张同花同点牌有不同编号。
    twin=next(i for i,c in enumerate(deck) if c==d.face_up_card and i!=chosen)
    assert twin!=d.face_up_id
