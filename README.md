# guandan_ai

[中文](#中文) · [English](#english)

## 中文

四人两队掼蛋桌面程序，支持 macOS / Windows、规则 AI、人机对战与可选 DeepSeek。
最近整理日期：2026-10-24。界面语言为中文；本说明及牌面规范均提供中英文。

### 启动

Python 3.11+，需安装 Tkinter。运行时仅使用标准库，无需 OpenAI SDK 或 keyring。
从项目根目录运行：

```bash
# macOS
python3 -m venv .venv
.venv/bin/python gui.py
# 查看四家手牌的规则 AI 观察器
.venv/bin/python viewer.py
# 引擎健康检查与测试
.venv/bin/python -m game_engine
.venv/bin/python tests/run_all.py
```

```powershell
# Windows：使用 Windows 本机 Python，不要复制 macOS 的 .venv
py -3 -m venv .venv
.venv\Scripts\python.exe gui.py
.venv\Scripts\python.exe viewer.py
.venv\Scripts\python.exe tests\run_all.py
```

也可在合适的虚拟环境内直接使用 `python gui.py`。代码可同步，虚拟环境和密钥不跨系统复制。

### GUI 与操作

- AI1下方、AI2右方、AI3上方、AI4左方；AI1/AI3为A队，AI2/AI4为B队。
- “新局”重新开始观察比赛；“单步”推进一手，“自动播放”连续运行，再按暂停。
  播放中按单步先暂停。GUI隐藏AI2～AI4手牌；viewer显示四家手牌。
- “人机对战”从2开始新比赛，AI1由人操作。轮到AI1时暂停等待，合法动作后自动继续。
  “出牌、过牌、进贡、还贡”按阶段启用；使用紧凑按钮、Arial 12号粗体、金色可用文字、灰色禁用文字，上方留白。
- 中央出牌区占3/5，记录区占2/5。四个出牌框保持上下左右布局；AI2标题靠右，其余靠左。
- 每局开始四家等待；首个动作后仅当前行动者显示“等待出牌”，未行动的其他玩家留空。
  已行动者保留上一手牌或PASS，收回牌权不清空全桌。出完显示头游、二游、三游、末游。
- PASS约三张牌宽，白色圆角框高度贴合大字。AI1初始27张牌一行显示；收贡时可暂时有28张。
- 日志共用 `turn_log.py`，包含动作、排名、接风、规则理由、进还贡及升级。
  当前为窗口内日志；自动导出和统计窗口尚未实现。

### 游戏规则

- 两副牌共108张，每人27张。全桌使用同一个本局级牌，双方升级进度独立。
  例如A升到5后全桌打5；B随后从2升到3，则全桌打3，A进度仍为5。
- 胜队为头游所在队；队友为二/三/末游时分别升3/2/1级。某队在A级双下结束整场比赛。
- 首局随机抽普通明牌（王重抽）再插回牌堆。A=1、J=11、Q=12、K=13；从AI1按
  AI1→AI2→AI3→AI4计数确定起牌者，逐张发牌，拿到指定明牌者首出。两副同牌用唯一编号区分。
- 后续局单贡由末游给头游；双贡按大贡给头游、小贡给二游，同大时上局三游优先。
  单贡末游首出，双贡大贡者首出；抗贡由上局头游首出。
- 单贡者有两张大王，或双贡者合计有两张大王，抗贡。进贡选最大可贡牌，保护两张红心级牌。
- 还贡牌面必须为2～10（含10），不要求小于贡牌；自动还贡选合法牌中单张力度最小者。
  人机模式AI1手动选贡牌、还牌。交换校验失败不提交半完成的自动换牌。
- 接风：最后出牌者已走完且其余玩家全过，由仍有牌的队友领出。有人压住则正常继续；
  若队友也走完，交给顺序下一位有牌者。
- 支持单张、对子、三张、三带二、固定五张顺子、固定三组连对、两组以上钢板、4～8炸、同花顺、四王炸。
  顺子连续序列不含2和王。红心级牌可百搭但不能代王，单出按级牌大小。
  多种解释跟牌时选择能压过上一手的最大解释。详见 [规则说明](rules_design.md)。

### 规则 AI 与限制

先整理成不重复用牌的组合；优先处理实际力度均不超过10的小单、对子、三张、三带二，
不为最小点数拆完整牌型。有普通组时保留炸弹/同花顺；无明显小组时优先减少手数。
能一手走完优先走完；对手报单优先完整多张，否则最大单张。
队友控牌默认让牌，允许直接走完或封堵报单下家；自身偏弱时可送小散单帮助报单队友。
这些判断只用自身手牌和公开信息，属于贪心启发式，不保证最优分组或提高胜率。

识别器支持复杂红心配，但AI候选目前只主动补对子、三张和炸弹；复杂百搭顺子等可人工选择，
尚未完整枚举。当前跟牌逻辑仍较简单。LLM也受候选生成范围限制。

### DeepSeek 与开关

1. 打开“LLM设置”，粘贴创建时复制的完整API Key，或读取本机已存密钥。
2. 默认模型 `deepseek-flash`，可选择/填写账户支持的模型。点击“测试连接”（会产生API用量）。
3. 选择一个LLM座位并保存；成功自动关闭，失败保留提示。也可用关闭按钮或Esc退出。
4. 在主界面打开“接入 LLM”。每次启动默认关闭；开关从下一动作生效，保留当前牌局。
   关闭恢复规则AI，旧的在途回答不执行；已发送的请求仍可能收费。
5. 人机模式AI1始终由人操作；可选AI2/AI4为对手，AI3为队友。当前仅支持一个LLM座位，
   两队多模型配置尚未实现。viewer保持全规则AI。

模型只接收自身手牌、公开信息及合法动作编号，返回编号和简短理由。
请求后台执行，25秒网络超时、单次尝试、非思考模式、最多256输出token。
失败或无效编号由规则AI接管，日志明确区分。测试连接独立于主界面开关。

| 系统 | 密钥 | 普通设置 |
|---|---|---|
| macOS | 系统钥匙串，服务 `guandan_ai.deepseek` | `~/Library/Application Support/guandan_ai/llm.json` |
| Windows | 当前用户的凭据管理器，同名通用凭据 | `%LOCALAPPDATA%\guandan_ai\llm.json` |

不将密钥写入源码、日志或配置文件；首次换电脑须重新保存。拒绝带星号等遮掩文本。
macOS补充加载 `/etc/ssl/cert.pem`，不关闭TLS或主机名验证。
提示区分证书、DNS、超时、网络、无效JSON和HTTP认证/余额错误。
401请检查完整密钥，402检查余额。模型可用性及费用以服务商为准。

### 目录与文档

| 文件/目录 | 职责 |
|---|---|
| `game_engine/` | 唯一规则实现：牌、发牌、识别、比较、结算、进贡、候选 |
| `agents/` | 观测动作接口、规则AI、DeepSeek及兼容LLM客户端 |
| `match_runner.py`, `game_series.py` | 单局调度、多局升级 |
| `gui.py`, `viewer.py` | 人机牌桌、全手牌观察器 |
| `benchmark.py`, `benchmark_gui.py` | 独立牌局统计、两队配置、日志导出 |
| `gui.spec` | PyInstaller打包配置，需在目标系统安装打包工具 |
| `card_ui.py`, `play_display.py`, `turn_log.py` | 共享牌面、PASS、动作日志 |
| `llm_dialog.py`, `llm_settings.py` | 设置界面、系统凭据、后台调用 |
| `tests/` | 无外部依赖规则测试和桌面回归 |
| `assets/card_style/` | 保留原始参考图、预览与[双语规范](assets/card_style/README.md) |
| [CHANGELOG](CHANGELOG.md) | 本阶段变更与清理记录 |
| [清理记录](docs/cleanup.md) | 缓存删除清单及哈希、保留项 |
| [维护说明](docs/maintenance.md) | 接口、验证、遗留限制 |
| [后续计划](docs/development_plan.md) | 当前状态与明确暂缓的功能 |
| [Apple平台开发与发布规划](docs/apple_platform_plan.md) | iPhone、iPad、Mac方案及App Store准备（规划阶段） |
| `docs/archive/` | 历史设计资料，不作为当前功能说明 |

### 验证与阶段状态

2026-10-24本机 macOS（项目 `.venv`，Python 3.13.3）84项核心测试通过。
以下四组桌面回归的既有记录通过（包括250步一致性和9小局完整人机比赛）；本次未重跑。
核心测试：`python tests/run_all.py`。桌面会话中分别运行：

```bash
python tests/gui_smoke.py
python tests/gui_modes_smoke.py
python tests/gui_llm_smoke.py
python tests/gui_play_status_smoke.py
```

LLM桌面测试使用模拟网络和凭据，不产生付费调用；Win32读写有模拟测试。
用户已确认Windows实际运行和DeepSeek真实连接成功；本次整理的自动回归在macOS运行，
不代表本次再次完成Windows实机验证。独立牌局统计窗口现见文末入口；旧验证记录不代表新统计程序的结果。

## English

A four-player, two-team Guandan desktop game for macOS and Windows, with rule-based AI,
human play and optional DeepSeek decisions. Last reviewed on 2026-10-24.
The application UI is Chinese; this README and the card-style README are bilingual.

### Running

Requires Python 3.11+ with Tkinter. Runtime uses only the standard library: no OpenAI SDK or keyring.
Run from the project root using the macOS or Windows commands above. Create a separate virtual
environment on each platform; never reuse the macOS `.venv` on Windows.
`gui.py` is the human/observer table, `viewer.py` shows all four hands, and
`python -m game_engine` runs a minimal engine health check.

### Controls and display

- AI1 sits below, AI2 right, AI3 above and AI4 left. AI1/AI3 form team A; AI2/AI4 form team B.
- New Game restarts observer mode. Single Step advances one action; during autoplay it first pauses.
  GUI hides AI2–AI4 hands; viewer reveals all hands.
- Human Play starts a new series at level 2. AI1 selects cards and uses Play, Pass, Tribute or Return.
  Other players advance automatically until the next human action. Buttons are compact, Arial 12 bold,
  gold when enabled and gray when disabled, with space above them.
- The central play area occupies 3/5 of the height; the scrolling log occupies 2/5.
  Four play boxes keep their cross layout; AI2's caption is right aligned, the others left aligned.
- At round start all seats say Waiting. After the first action only the current seat says Waiting;
  unacted seats are blank, and other seats retain their latest play or PASS. Reclaiming the lead does
  not clear the table. Finished seats show first/second/third/last place in Chinese.
- PASS is about three card widths, with a white rounded box fitted to the text height.
  AI1's initial 27 cards fit on one row; receiving tribute may temporarily produce 28 cards.
- Shared on-screen logs include actions, ranks, lead transfer, rule-AI reasons, tribute and advancement.
  Automatic log-file export and the statistics window are not implemented.

### Rules

Two decks contain 108 cards, dealt as 27 per player. Both teams share the current round level,
while their advancement progress is independent. If A advances to 5, everyone plays level 5;
if B later advances from 2 to 3, everyone plays level 3 while A retains progress 5.
The first finisher's team wins the round and advances 3/2/1 levels when its partner finishes
second/third/last. A first-and-second finish while playing at that team's A level ends the series.

For the opening deal, draw a non-joker face-up card and reinsert it randomly. Count A=1, J=11,
Q=12, K=13 from AI1 in AI1→AI2→AI3→AI4 order to choose the first recipient. Deal one card at a time;
the player receiving that exact face-up card leads. Unique IDs distinguish duplicate cards.

Later rounds use tribute. Single tribute goes from last to first; double tribute sends the larger
card to first and smaller to second, with the previous third finisher taking priority on equal cards.
The single giver or larger double giver leads. Two big jokers held by the single giver, or jointly
by double givers, prevent tribute; the previous first finisher then leads. Both heart level cards
are protected from giving tribute. Return cards must have face ranks 2–10 inclusive, regardless of
level status, and need not be lower than the received card. Automatic returns choose the lowest
single-card strength; human AI1 selects manually. Failed automatic exchange validation does not
commit a partial exchange.

When a player's final play is followed by passes from all remaining players, their active partner
receives the lead (接风). Any covering play replaces the last play normally. If the partner has also
finished, the next active seat leads.

Supported types: singles, pairs, triples, full houses, fixed five-card straights, exactly three
consecutive pairs, at least two consecutive triples, 4–8-card bombs, straight flushes and four jokers.
Straight sequences exclude 2 and jokers. Heart level cards are wild but cannot replace jokers;
a single heart level card retains level strength. Ambiguous responses choose the strongest
interpretation that beats the previous play. See [rules](rules_design.md) for implementation details.

### Rule AI and limitations

A greedy partition assigns each card to one group. The AI first sheds small singles, pairs, triples
or full houses whose cards all have strength at most 10, without splitting a completed group merely
to play a low rank. It retains bombs/straight flushes while ordinary groups remain; otherwise it
prefers reducing the number of remaining plays. A legal immediate finish takes priority.
Against a one-card opponent it leads a complete multi-card group or, if none exists, its largest single.
It normally yields to its partner, except for an immediate finish or blocking a one-card next opponent.
A weak hand may feed a loose low single to a one-card partner. Only private own-hand and public data
are used. These heuristics do not guarantee an optimal partition or better win rates.

The recognizer supports complex wild-card interpretations, but AI candidates only actively complete
pairs, triples and bombs with wild cards. Humans can select more complex wild-card plays; exhaustive
AI enumeration remains pending. Follow-play strategy is still basic; LLM choices share these limits.

### DeepSeek setup

Open LLM Settings, paste the complete key shown when it was created (or load the saved key), choose
an available model and one seat, test the connection, then save. The configured default is
`deepseek-flash`; service availability and pricing may change. Testing is a real, billable request.
Successful saving closes the window; errors remain visible. Close/Esc also dismisses it.

Enable **接入 LLM** on the main table when needed. Every launch defaults to OFF. Switching affects
the next action without redealing; OFF restores rule AI and ignores old pending responses. Requests
already sent may still incur charges. Human AI1 always remains human: select AI2/AI4 as an opponent
or AI3 as a partner. Only one LLM seat is currently supported; viewer remains rule-only.
Connection testing is available independently of this switch.

The model receives its own hand, public state and legal action IDs, then returns an ID and short reason.
Requests run in the background with a 25-second network timeout, one attempt, thinking disabled and
up to 256 output tokens. Failure or invalid IDs trigger a clearly logged rule-AI fallback.

Keys are stored in macOS Keychain or the current Windows user's Credential Manager under
`guandan_ai.deepseek`, never in project files, configuration or logs. The non-secret settings paths
are listed in the platform table above. Keys must be saved separately on a new computer. Masked keys
containing asterisks are rejected. macOS additionally loads `/etc/ssl/cert.pem` while retaining TLS
certificate and hostname checks. Errors distinguish certificates, DNS, timeouts, network, JSON and
HTTP failures; check the full key for 401 and balance for 402.

### Layout, documentation and verification

`game_engine/` is the sole rules implementation; `agents/` contains observations, actions and AI.
`match_runner.py` handles a round and `game_series.py` handles advancement. `gui.py`/`viewer.py` are
entrypoints; `card_ui.py`, `play_display.py` and `turn_log.py` provide presentation.
`llm_dialog.py`/`llm_settings.py` manage connections and credentials. `tests/` contains core and desktop
regressions; `assets/card_style/` preserves the reference image and bilingual style guide.

See [CHANGELOG](CHANGELOG.md), [maintenance notes](docs/maintenance.md),
[current roadmap](docs/development_plan.md) and [card style](assets/card_style/README.md).
See also the [Apple platform development and distribution plan (Chinese)](docs/apple_platform_plan.md) for proposed iPhone, iPad and Mac versions; these clients are not yet implemented.
`docs/archive/` contains historical proposals, not current functionality.

On 2026-10-24, all 84 core tests passed on macOS using the project `.venv` (Python 3.13.3).
Earlier desktop checks passed, including 250 matched actions and a nine-round human-mode series;
these four desktop checks were not rerun for this directory cleanup. Run `python tests/run_all.py`, then the four desktop scripts
listed above in a desktop session.
LLM GUI tests use fake network/credentials and make no paid requests; Windows API boundaries are mocked.
The user has confirmed Windows operation and a real DeepSeek connection. This documentation-cleanup
regression runs on macOS, not a new Windows validation. The configurable benchmark and log export are now available through benchmark_gui.py; separate compatible LLM endpoints can be selected for each team.

## 独立牌局统计测试 / Independent-round benchmarks

运行 `python benchmark_gui.py`，选择250、500、1000局或自定义局数。支持规则队、LLM队及不同兼容LLM之间对战；详见[测试程序设计](docs/benchmark_design.md)。先用少量局数核实参数和连接，再进行可能计费的LLM批量测试。

Run `python benchmark_gui.py` for configurable independent rounds, natural-pattern statistics and per-run logs. Each team may use rules or a compatible LLM. Start with a small trial; LLM calls may incur charges. See the [design (Chinese)](docs/benchmark_design.md).
