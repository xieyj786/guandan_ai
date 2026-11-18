"""对局随机来源；指定种子用于测试，不指定则每局取系统随机种子。"""
from dataclasses import dataclass
import secrets

NORMAL = "正常游戏"
REPLAY = "测试与复盘"
MODES = (NORMAL, REPLAY)


def resolve_seed(seed: int | None) -> int:
    return secrets.randbits(256) if seed is None else seed


@dataclass(frozen=True)
class SeedSequence:
    base_seed: int | None = None

    @property
    def mode(self) -> str:
        return NORMAL if self.base_seed is None else REPLAY

    def for_round(self, number: int) -> int:
        if number < 1:
            raise ValueError("局号从1开始")
        return resolve_seed(None if self.base_seed is None else self.base_seed + number - 1)


def command_seed() -> int | None:
    """命令行入口：省略种子为正常游戏，指定种子为测试与复盘。"""
    import argparse
    parser = argparse.ArgumentParser(description="默认正常游戏；指定 --seed 切换测试与复盘")
    parser.add_argument("--seed", type=int, help="测试与复盘种子（整数）")
    return parser.parse_args().seed
