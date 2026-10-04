"""两个桌面入口共享逐手出牌记录格式。"""
from game_engine.card import card_display


def format_turn_log(match, player_index, before_count, turn):
    name = match.agents[player_index].name
    if len(match.hands[player_index]) < before_count:
        if match.last_play is None:
            raise RuntimeError("出牌后缺少出牌记录")
        messages = [f"{turn}. {name} 出 " + " ".join(card_display(c) for c in match.last_play.cards)]
        if player_index in match.finish_order:
            messages.append(f"{name} 出完，第 {match.finish_order.index(player_index)+1} 名。")
    else:
        messages = [f"{turn}. {name} 过牌"]
        if match.last_play is None:
            wind = (match.last_player in match.finish_order and match.last_player is not None
                    and match.current_player == (match.last_player + 2) % 4)
            prefix = "接风，" if wind else ""
            messages.append(f"{match.agents[match.current_player].name} {prefix}重新领出。")
    reason = getattr(match, "last_rule_reason", None)
    if reason and reason[0] == player_index and reason[1]:
        messages.append(f"{name}〔规则AI〕：{reason[1]}")
    match.last_rule_reason = None
    return messages
