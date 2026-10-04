"""运行核心引擎的最小健康检查。"""

from .card import Card, Rank, Suit
from .identify import identify_card_type


def main() -> None:
    card_type = identify_card_type([Card(Suit.SPADE, Rank.ACE)], Rank.TWO)
    print(f"guandan_ai 核心引擎可用：{card_type.category.name}")


if __name__ == "__main__":
    main()
