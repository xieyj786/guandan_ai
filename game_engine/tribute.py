"""
进贡 / 抗贡 / 还贡状态机。见 rules_design.md 3 节。
"""

from dataclasses import dataclass

from .card import Card, Rank, Suit, is_level_card, single_card_power
from .round_result import Player, RoundResult, TributeType


@dataclass
class TributeAssignment:
    """一次进贡的来源方与接收方映射。"""
    giver: Player
    receiver: Player
    tribute_card: Card
    return_card: Card | None = None  # 还贡完成后填入


@dataclass
class TributeOutcome:
    anti_tribute: bool
    first_player: Player
    assignments: list[TributeAssignment]  # 抗贡时为空列表


def count_big_jokers(hand: list[Card]) -> int:
    return sum(1 for c in hand if c.suit == Suit.JOKER and c.rank == Rank.BIG_JOKER)


def check_anti_tribute(tribute_players: list[Player], hands: dict[str, list[Card]]) -> bool:
    """
    抗贡判定。

    Args:
        tribute_players: 需要上贡的玩家（单贡1人，双贡2人）
        hands: player_id -> 手牌列表（判定时手牌应为进贡前的完整手牌）
    """
    big_joker_counts = [count_big_jokers(hands[p.player_id]) for p in tribute_players]

    if len(tribute_players) == 1:
        return big_joker_counts[0] == 2

    if len(tribute_players) == 2:
        if 2 in big_joker_counts:
            return True
        if big_joker_counts[0] == 1 and big_joker_counts[1] == 1:
            return True
        return False

    raise ValueError("tribute_players 长度必须为 1 或 2")


def determine_tribute_card(hand: list[Card], level_rank: Rank) -> Card:
    """
    选出进贡者要上贡的牌：手中最大的牌；若最大牌是红心级牌，
    则改贡"次大"的牌（红心级牌保护）。
    """
    eligible = [c for c in hand if not (c.suit == Suit.HEART and is_level_card(c, level_rank))]
    if not eligible:
        raise ValueError("没有可进贡的牌（红心级牌受保护）")
    return max(eligible, key=lambda c: single_card_power(c, level_rank))


def resolve_tribute(round_result: RoundResult, hands: dict[str, list[Card]], level_rank: Rank,
                    team_levels: dict[str, Rank] | None = None) -> TributeOutcome:
    """
    进贡主流程：抗贡判定 -> 进贡牌选择 -> 贡牌分配 -> 首出权确定。
    还贡（return_card）由调用方在收贡方选定还贡牌后另行调用 apply_return_tribute 填入。
    """
    def level_of(player):
        return level_rank  # team_levels 仅为兼容参数，不参与本局牌力判断

    tribute_players = round_result.tribute_players

    if check_anti_tribute(tribute_players, hands):
        return TributeOutcome(
            anti_tribute=True,
            first_player=round_result.head_player,
            assignments=[],
        )

    if round_result.tribute_type == TributeType.SINGLE:
        giver = tribute_players[0]
        tribute_card = determine_tribute_card(hands[giver.player_id], level_of(giver))
        assignment = TributeAssignment(
            giver=giver, receiver=round_result.head_player, tribute_card=tribute_card,
        )
        return TributeOutcome(anti_tribute=False, first_player=giver, assignments=[assignment])

    if round_result.tribute_type == TributeType.DOUBLE:
        giver_a, giver_b = tribute_players
        card_a = determine_tribute_card(hands[giver_a.player_id], level_of(giver_a))
        card_b = determine_tribute_card(hands[giver_b.player_id], level_of(giver_b))

        power_a = single_card_power(card_a, level_of(giver_a))
        power_b = single_card_power(card_b, level_of(giver_b))

        if power_a >= power_b:
            bigger_giver, bigger_card = giver_a, card_a
            smaller_giver, smaller_card = giver_b, card_b
        else:
            bigger_giver, bigger_card = giver_b, card_b
            smaller_giver, smaller_card = giver_a, card_a

        assignments = [
            TributeAssignment(giver=bigger_giver, receiver=round_result.head_player, tribute_card=bigger_card),
            TributeAssignment(giver=smaller_giver, receiver=round_result.second_player, tribute_card=smaller_card),
        ]
        # 首出权归"贡出较大那张牌的人"
        return TributeOutcome(anti_tribute=False, first_player=bigger_giver, assignments=assignments)

    raise ValueError(f"未知的 tribute_type: {round_result.tribute_type}")


def is_valid_return_card(card: Card) -> bool:
    """按牌面点数还贡：2～10（含10），不接受 J/Q/K/A 和大小王。"""
    return card.suit != Suit.JOKER and Rank.TWO <= card.rank <= Rank.TEN


def apply_return_tribute(assignment: TributeAssignment, return_card: Card, level_rank: Rank) -> None:
    """还贡牌面须小于等于10；保留 level_rank 参数以兼容既有调用。"""
    if not is_valid_return_card(return_card):
        raise ValueError("还贡必须使用牌面点数小于等于10的牌（2～10）")
    assignment.return_card = return_card


def exchange_tribute(round_result: RoundResult, hands: dict[str, list[Card]],
                     level_rank: Rank, team_levels: dict[str, Rank] | None = None) -> TributeOutcome:
    """在副本上完成自动进还贡，全部合法后一次提交；异常不改变原手牌。

    自动还牌面 2～10 中单张力度最小的牌；级牌不改变还贡资格。
    """
    outcome = resolve_tribute(round_result, hands, level_rank, team_levels)
    if outcome.anti_tribute:
        return outcome
    working = {player: list(cards) for player, cards in hands.items()}
    for assignment in outcome.assignments:
        giver = working[assignment.giver.player_id]
        receiver = working[assignment.receiver.player_id]
        giver.remove(assignment.tribute_card)
        receiver.append(assignment.tribute_card)
    for assignment in outcome.assignments:
        receiver = working[assignment.receiver.player_id]
        level = level_rank
        eligible = [card for card in receiver if is_valid_return_card(card)]
        if not eligible:
            raise ValueError(f"{assignment.receiver.player_id} 没有牌面点数小于等于10的合法还贡牌")
        returned = min(eligible, key=lambda card: single_card_power(card, level))
        apply_return_tribute(assignment, returned, level)
        receiver.remove(returned)
        working[assignment.giver.player_id].append(returned)
    for player, cards in working.items():
        hands[player][:] = cards
    return outcome


class TributeSession:
    """可暂停的进还贡流程：先确认所有贡牌，再逐一还贡。"""

    def __init__(self, result, hands, level_rank, human_player):
        self.hands = hands
        self.level_rank = level_rank
        self.human_player = human_player
        self.outcome = resolve_tribute(result, hands, level_rank)
        self.tasks = []
        if not self.outcome.anti_tribute:
            self.tasks = [("tribute", a) for a in self.outcome.assignments]
            self.tasks += [("return", a) for a in self.outcome.assignments]
        self.position = 0
        self.advance_auto()

    @property
    def complete(self):
        return self.position == len(self.tasks)

    @property
    def pending(self):
        return None if self.complete else self.tasks[self.position]

    def actor(self):
        kind, assignment = self.pending
        return assignment.giver.player_id if kind == "tribute" else assignment.receiver.player_id

    def eligible_cards(self):
        if self.complete:
            return []
        kind, assignment = self.pending
        hand = self.hands[self.actor()]
        if kind == "return":
            return [c for c in hand if is_valid_return_card(c)]
        power = single_card_power(assignment.tribute_card, self.level_rank)
        return [c for c in hand if not (c.suit == Suit.HEART and c.rank == self.level_rank)
                and single_card_power(c, self.level_rank) == power]

    def _apply(self, card):
        if card not in self.eligible_cards():
            raise ValueError("进贡须选最大非红心级牌；还贡须选牌面2～10的一张手牌")
        kind, assignment = self.pending
        if kind == "tribute":
            assignment.tribute_card = card
        else:
            apply_return_tribute(assignment, card, self.level_rank)
            self.hands[assignment.receiver.player_id].remove(card)
            self.hands[assignment.giver.player_id].append(card)
        self.position += 1
        # 所有贡牌选择完毕后统一转移，避免后续选择受收牌影响。
        if kind == "tribute" and self.pending and self.pending[0] == "return":
            for item in self.outcome.assignments:
                self.hands[item.giver.player_id].remove(item.tribute_card)
                self.hands[item.receiver.player_id].append(item.tribute_card)

    def advance_auto(self):
        while not self.complete and self.actor() != self.human_player:
            eligible = self.eligible_cards()
            if not eligible:
                raise ValueError(f"{self.actor()} 没有合法还贡牌")
            self._apply(min(eligible, key=lambda c: single_card_power(c, self.level_rank)))

    def submit(self, card):
        if self.complete or self.actor() != self.human_player:
            raise ValueError("当前无需人工进还贡")
        self._apply(card)
        self.advance_auto()
