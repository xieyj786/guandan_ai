# Play 离线版与移动端准备

程序采用简单名称 `play.py`，桌面窗口标题为“掼蛋 · Play”。它基于当前 `gui.py` 的
非 LLM 功能，保留规则修正和牌面改进，并不回滚到旧版本的规则。

## 启动与操作

在项目根目录使用带 Tkinter 的 Python 3.11+：

```bash
python play.py
```

“人机对战”由你控制 AI1，其他座位使用规则 AI；支持选牌、出牌、过牌、进贡和还贡。
“新局”回到规则 AI 观察模式，“单步”推进一手，“看AI对战”自动播放，再次点击暂停。
扑克牌、红心配和选牌提示与 `gui.py` 使用同一组件。

该入口不加载 LLM 配置或凭据，不包含模型连接、模型统计和防睡眠进程。
原有 `gui.py`、`viewer.py` 保留各自用途。

## 代码边界

结构整理后，根目录文件是兼容入口，正式实现和分层约束见 [项目架构](architecture.md)。

| 文件 | 职责 | 后续移动端复用 |
| --- | --- | --- |
| `presentation/play.py`（入口 `play.py`） | Tk 窗口、选牌、按钮、计时器和日志显示 | 替换为触摸界面 |
| `gameplay/offline.py`（兼容 `play_game.py`） | 对局状态、人工动作、规则 AI 步进、进还贡和升级 | 可复用 Python 逻辑或作为移植参照 |
| `gameplay/match.py` | 单局轮转和动作校验 | 核心逻辑 |
| `game_engine/` | 发牌、牌型、红心配、比较、进贡和终局规则 | 核心逻辑 |
| `gameplay/contracts.py`、`strategy/rule_agent.py`、`strategy/planner.py` | 规则 AI 及其数据结构与策略 | 核心逻辑及其内部依赖 |
| `gameplay/series.py` | 共享级牌序列 `LEVELS` | 当前控制层依赖 |
| `gameplay/turn_log.py` | 文本出牌记录 | 可复用或改为移动端展示 |
| `presentation/cards.py`、`presentation/play_display.py` | Tk 牌面与 PASS 绘制 | 按 `assets/card_style/` 规范重新实现绘制 |

上述是职责说明，不是最小打包清单。保留完整 `game_engine/`、`strategy/`、`gameplay/` 及所需兼容入口和当前文件间的
内部导入关系；不要只复制表中几个文件后就认为已具备完整依赖。

`play_game.py` 不依赖 Tk、LLM、网络、钥匙串或桌面计时器。控制层封装 `Match` 的内部
动作方法，后续界面从下面的公开接口提交操作，不必自行操作引擎内部方法。

## 移动界面接口

```python
from gameplay.offline import PlayGame

game = PlayGame()
game.new_game(human_mode=True, seed=101)
state = game.snapshot()
```

公开接口：

- `new_game(human_mode=True, seed=...)`：开始比赛；省略种子时递增种子。
- `snapshot()`：取得独立的字典和列表，可用 `json.dumps()` 序列化。
- `step()`：让下一名规则 AI 行动一次；等待人工动作或比赛结束时返回 `False`。
- `play([手牌编号, ...])`：提交 AI1 的出牌。
- `pass_turn()`：提交 AI1 过牌。
- `exchange(手牌编号)`：完成当前人工进贡或还贡。
- `drain_events()`：取出并清空新增文本记录。

状态包含手牌、桌面各座位上一手、当前玩家、游次、级牌、队伍进度、
`human_can_play`、`can_pass`、`pending_exchange` 和 `eligible_exchange_indices`。
按 `human_can_play` / `pending_exchange` 等状态显示操作按钮，否则定时调用 `step()`。
每个动作后重新读取状态、绘制界面并读取新增日志；非法人工动作抛出 `ValueError`，
界面显示错误后允许重新选择。当前规则 AI 调用是同步的；如移动界面使用后台任务，
所有动作应在同一串行队列执行，避免同时修改对局状态。

手牌 `index` 对应当前手牌数组的位置，能够区分两副牌中相同花色点数的实体牌。
界面排序后必须保留该编号；每次动作后刷新，不能跨动作缓存编号。
状态包含四家完整手牌，仅用于本机离线游戏。人机界面应隐藏其他三家的手牌，
它不是可直接对外发送的联网对战协议。

## 下一步 iPhone / iPad 工作

当前已完成对局逻辑和 Tk 界面的分离，并提供无需启动窗口的规则及流程测试。
Tk 桌面界面不能直接视为 iOS 界面；下一步仍需实现触摸选牌、横竖屏布局、安全区域、
应用进入后台及恢复等平台行为。移动端继续遵循 `assets/card_style/README.md`，
保留红心配和选牌状态。

后续可按实际工程选择保留 Python 控制层，或将其与规则引擎移植到移动端语言。
选定运行方式后，再处理 iOS 工程、资源、签名、真机测试及发布。本次没有创建 iOS 工程，
没有在 iPhone 或 iPad 上验证，也没有新增存档/恢复接口。

## 验证

```bash
python tests/run_all.py
# 必须在桌面会话运行；创建 Tk 窗口并在结束后关闭
python tests/play_smoke.py
```

新增控制层测试验证无 UI / LLM 依赖、JSON 状态、非法动作不修改牌局、等待人工操作，
以及通过手牌编号完成包括进还贡在内的整场升级比赛。
桌面测试核对与观察器连续 250 手一致，并通过人工按钮入口完成整场比赛。
