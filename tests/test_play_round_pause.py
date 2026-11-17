"""Deferred desktop round transitions preserve the result until the next step."""
from gameplay.offline import PlayGame


def test_deferred_round_keeps_finished_table_until_next_step():
    game = PlayGame(defer_round_start=True)
    game.new_game(seed=42)
    finished_match = game.match
    for _ in range(1000):
        game.step()
        if game.pending_round_result is not None:
            break
    assert game.pending_round_result is not None
    assert game.match is finished_match
    assert len(game.match.finish_order) == 4
    assert game.round_number == 1
    messages = game.drain_events()
    assert any("下一局全桌打" in message for message in messages)
    assert not any("第 2 局发牌" in message for message in messages)
    game.step()
    assert game.pending_round_result is None
    assert game.round_number == 2
    assert game.match is not finished_match
    assert game.turns == 0
    assert all(len(hand) == 27 for hand in game.match.hands)


def test_new_game_clears_pending_round():
    game = PlayGame(defer_round_start=True)
    game.new_game(seed=42)
    game.pending_round_result = object()
    game.new_game(seed=43)
    assert game.pending_round_result is None
    assert game.round_number == 1
