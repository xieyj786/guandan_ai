# 发牌机制、随机模式与策略对照

更新：2026-11-18。本文说明当前 Python 实现；独立 Swift/iOS 不属于本次源码提交范围。

## 模式与入口

| 入口 | 默认 | 测试与复盘方式 |
| --- | --- | --- |
| `play.py` | 正常游戏；每局独立取系统随机种子 | 界面不提供切换，开发验证可调用 `new_game(seed=42)` |
| `gui.py`、`viewer.py` | 正常游戏 | 选择“测试与复盘”，输入整数种子，再开始新游戏 |
| `match_runner.py`、`game_series.py` | 正常游戏 | 命令行添加 `--seed 42` |
| `benchmark.py`、`benchmark_gui.py` | 固定种子的对照评测 | 沿用现有种子、批次及换位配置，不受游戏界面选项影响 |

界面的模式和基础种子在**新游戏**时读取，整场升级比赛沿用该配置；修改待选项不会改变当前比赛或下一局的随机来源。测试模式无效种子会阻止新游戏，正常模式忽略隐藏的种子输入。

## 种子如何使用

`gameplay/randomness.py` 负责来源与每局种子管理，`game_engine/deck.py` 负责牌堆、洗牌与分发，不依赖窗口或策略。

- 正常游戏每局调用 `secrets.randbits(256)`，取得操作系统随机源支持的新种子，再交给 `random.Random(seed)` 完成洗牌与抽牌。
- 测试与复盘第 n 局使用“基础种子 + n - 1”，保留既有固定牌局序列；0和负整数也可作为明确种子。
- `Match(seed=None)` 在首次 `prepare()` 时生成并保留实际种子，重复准备不会重发牌或重新取种子。
- 明牌点数仅决定起牌座位，不作为种子；不根据人类/AI、座位、难度或牌力重排牌。

这是高质量系统种子驱动的伪随机过程，并非声称物理真随机或不可破解的联网发牌协议。独立随机取种子不保证绝不重复，连续出现强牌、弱牌、同花集中等情况也可能是正常结果。重复洗牌不等于增加独立随机信息。

## 108张牌如何发出

1. 建立两副标准扑克，共108张，包含4张王。
2. 首局洗牌后随机抽明牌，抽到王重抽；将选中的普通牌随机插回108个位置之一。
3. A算1，2～10按牌点，J/Q/K算11/12/13。从AI1沿AI1→AI2→AI3→AI4计数，确定第一张发给谁。
4. 从起牌者按同一顺序逐张轮发，每人27张；谁拿到指定的那一张明牌，谁首出。首局使用0～107的实体编号区分双副同牌。
5. 后续局重新洗牌，按座位依次分配四段各27张，再按上一局结果执行进还贡/抗贡与首出规则。对均匀随机牌堆，分段分配与轮流分配的手牌分布等价。

现有明牌、牌型、红心配、进还贡和升级规则没有因模式切换而改变。

## 记录与复现边界

`Match.deal_record` 是可 JSON 序列化的记录，包含：

- `format`：`python-random-v1`，标识当前发牌方案，并非跨版本兼容承诺。
- `seed`：本局实际种子；`level_rank`、`team_levels`、`use_wildcards`：规则配置。
- `agents`：按座位排列的代理类型；不是策略参数、模型配置或代码版本快照。
- `hands_before_tribute`：按座位及发牌顺序保存的手牌，每张为 `[花色, 点数]`；后续进还贡不改写这份记录。
- `first_receiver`、`first_player`：首局明牌决定的起牌、首出座位（0～3）；后续局为 `None`，实际首出还取决于进还贡结果。

GUI、viewer、PlayGame 和 GameSeries 的 `round_records` 收集每局记录并附加 `round_number`；界面新游戏重置记录。PlayGame 的 `snapshot()` 还提供 `random_mode` 和 `round_seed`。这些都是本机离线数据，不是联网隐藏手牌的协议。

正常模式界面不显示种子；测试模式日志显示每局种子。Python记录目前保存在内存，关闭程序即丢失，没有自动保存或导出按钮。开发者可主动导出：

```python
import json
from pathlib import Path
from gameplay.offline import PlayGame

game = PlayGame()
game.new_game(seed=42)  # 省略 seed 则正常随机
Path("deal-records.json").write_text(
    json.dumps(game.round_records, ensure_ascii=False, indent=2), encoding="utf-8"
)
```

相同实现、Python版本和规则配置下，可使用记录的种子重现本局原始发牌；若重现后续局的进还贡，还需上一局结果。同一数字种子不保证 Python 与 Swift 的牌序一致。跨版本核对可对照明确手牌记录，但目前没有直接导入手牌的回放播放器。

完整对局复现还需要代码版本、策略参数、人工动作，以及可能的LLM输出和AI自身随机决策。种子不能单独重现这些行为；`round_records` 也不是完整事件日志。

## 策略改进与难度

随机模式与策略能力独立。新旧策略使用相同固定牌局、轮换座位和搭档，并保留不参与调参的验证牌局；先小批检查失败原因与记录完整性，再扩大评测。案例与结论应人工复核，流程见[策略持续改进](strategy_improvement.md)。

难度可以通过策略能力或计算预算分级，不以给某方好牌实现。本次不训练策略、不新增难度选项、不宣称棋力提高。

## 验证入口

- `python tests/run_all.py`：核心、架构、完整牌堆、明牌起牌、固定种子及正常模式随机源记录。
- `python tests/random_modes_smoke.py`：真实Tk模式切换、无效/隐藏种子、配置冻结与固定牌局。
- `python tests/gui_modes_smoke.py`、`python tests/play_smoke.py`：固定250步对照、暂停重置及人机进还贡。
- `python tests/viewer_layout_smoke.py`：观战器三种窗口尺寸、控件同排靠右、50%叠放与319宽右栏。

Windows验证由源码CI执行；本机macOS通过不等于Windows或真实LLM验证。项目继续仅发布源码，不生成新的gui.exe。
