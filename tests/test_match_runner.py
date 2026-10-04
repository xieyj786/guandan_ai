"""Match Runner 的端到端回归测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.rule_agent import RuleAgent
from match_runner import Match


def test_rule_agents_complete_a_full_round():
    match = Match(
        agents=[RuleAgent(f"AI{i}") for i in range(4)],
        seed=20260810,
        verbose=False,
    )
    result = match.run()

    assert len(result.finish_order) == 4
    assert len({player.player_id for player in result.finish_order}) == 4
    assert all(len(hand) == 0 for hand in match.hands)


if __name__ == "__main__":
    test_rule_agents_complete_a_full_round()
    print("PASS test_rule_agents_complete_a_full_round")
