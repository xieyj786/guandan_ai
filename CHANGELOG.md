## 2026-11-01 本地模型统计提速

- 整理本地客户端工厂的明确返回类型，修复连接测试的Pylance提示；统计窗口关闭时取消轮询定时器。补齐安装模块清单，并将新增LLM桌面回归纳入Windows打包检查。

- 将共享LLM优化接入主窗口（115项自动测试、原有GUI/人机回归及真实本地单步验证通过）：本地精简模式可选、窗口累计Token/请求耗时/自动动作/回退与实时等待显示，Mac模型运行时临时防睡眠；重开后过期动作丢弃但实际调用用量保留。
- 旧LLMAgent保留原响应协议，统一合法动作集合，跳过唯一动作并拒绝非法首出过牌或不能压牌。

- 精简协议改为显式动作编号，解码Schema约束合法ID；本局模型决策和回退实时累计。
- 修正版完成真实26局：0失败、0回退，耗时1:44:19，较上一轮少5.36%，总Token少8.56%；普通提示保留，实验协议显式选择。详见docs/benchmark_v3_validation_20261101.md。

- 第二轮试验：新增“LM Studio（实验）”使用结构化牌张/历史编码、固定系统说明和仅动作编号输出；普通LM Studio保留上一轮协议，全部合法动作及公开信息保留，主游戏窗口模式不变。

- 唯一合法动作自动执行并单独计数，避免不必要的模型调用与规则推荐规划。
- LM Studio使用保留全部公开信息和合法动作的紧凑提示；配置记录策略协议版本。
- 分开展示含系统睡眠的钟表时长与系统运行计时；Mac测试期间可防止空闲睡眠，结束自动释放。
- 历史轨迹离线复演：请求588降至304、剩余提示字符减少33.16%；未据此声称真实Token、模型强度或端到端速度已验证。

## 2026-10-31 独立牌局统计重设计

- 运行结束或手动停止自动输出benchmark_log_NNN.txt，包含程序名称、开始/结束时间、时长和全部汇总/逐局统计；编号自动递增且不覆盖旧文件。

- 新增按策略队伍汇总的请求次数、输入/输出/思考/缓存Token和请求耗时；实时显示总时长、暂停时长、当前决策等待及剩余时间粗估，数据导出至CSV/JSON。

- 统计窗口新增LM Studio类型，复用本地JSON Schema客户端，支持本地连接测试、模型/回环地址及10～600秒等待时间；本地模式禁用API Key。

- 每轮13副不同发牌分别用于级牌2至A，再固定手牌和首出位置交换策略队伍，共26局；支持50/100/500轮及小批验证。
- 增加换位前后、各级牌胜率和完整配对比较，记录轮次、级牌、配对编号与首出位置；失败和取消不计输。
- 配对样本不报告普通独立样本置信区间；保留自然牌型与LLM规则接管日志。

# 近期变更 / Recent changes

## 2026-10-28 发布整理 / Release preparation

- 保留并整理现有出牌尺寸、看AI对战按钮、人工动作闪烁提示改进。
- 修正文档过时的统计功能说明，增加 Windows 自动测试、打包、窗口检查与 Release 附件流程。
- 修复 Windows 回归中的 UTF-8 日志读取与模拟 macOS 证书路径断言。
- Preserve current GUI improvements; refresh documentation and add Windows release automation.


## 2026-10-25 出牌尺寸 / Played card size

- GUI出牌以AI1手牌宽高的2/3为目标，窗口默认高度增至850；四方布局与3:2区域比例保留，空间不足时整组缩小以免裁切。
- Played cards target two-thirds of the human hand size; default window height is 850. Existing layout remains, with fit-to-space fallback.


## 2026-10-24 目录整理 / Directory cleanup

- 删除可再生Python与Finder缓存，记录删除前哈希；保留环境、Windows构建记录、牌面参考图和全部有效功能。
- 更新README的目录说明与84项本机回归结果；源码、测试、打包配置和文档统一纳入GitHub同步。
- Removed regenerable caches with an audit trail; preserved environments and local Windows builds. Updated layout and local test status.

## 2026-10-24 固定三连对 / Fixed consecutive pairs

- 连对收紧为三对六张；识别层（含红心配）及AI候选生成同时拒绝四连对及更长连对。钢板不变。
- Consecutive pairs now require exactly three pairs; recognition and AI generation reject longer runs, including wildcard substitutions. Triple-run rules are unchanged.
- 本机84项回归通过；未重新生成或实测Windows exe，需在Windows用更新后的源码重新打包。
- 84 local regressions passed; Windows executables must be rebuilt and tested separately.

## 2026-10-23 独立牌局统计 / Independent-round benchmark

- 新增统计窗口、自定义局数、可选同牌换位、两队兼容LLM配置、自然牌型统计、胜率与日志。
- Added configurable runs, optional paired swaps, per-team compatible LLM setup, natural-pattern counts, win rates and logs.
- 支持动作边界暂停/停止；密钥不落盘；明确记录规则回退。
- Supports pause/stop at action boundaries, memory-only keys and explicit fallback counts.

## 2026-10-21 策略规划 / Strategy planning

- 增加可配置的多方案分组、炸后剩牌评估与队友控牌时的风险拦截；记录原则编号和决策信息。
- Added configurable alternative partitions, bomb remainder evaluation and risk-reducing partner interception with decision tracing.
- 新增残局回归；未改变游戏规则，尚无胜率提升验证。
- Added endgame regressions; game rules are unchanged and playing-strength gains remain unverified.

本阶段截至2026-10-04，按功能归纳，不将尚未实现的方案当作交付。
Milestone through 2026-10-04; grouped by feature rather than claiming unimplemented proposals.

## 2026-10-20：大小王牌面 / Joker artwork

- 按用户新参考图，用可缩放小丑图案替换五角星；小王黑色 JOKER，大王红色 JOKER。GUI 与 viewer 共用。
- Replaced joker stars with scalable jester artwork based on the new reference; black JOKER for the small joker and red JOKER for the big joker, shared by GUI and viewer.
- 保存原图于 `assets/card_style/joker_reference.png`；牌面状态边框和游戏规则保持不变。
- Preserved the reference image; card state borders and game rules remain unchanged.

## 规则与对局 / Rules and matches

- 统一为108张四家各27张；接通红心配识别、比较与候选；保护两张红心级牌。
- 本局级牌全桌共享，升级进度按队独立；A级双下结束整场。
- 单/双贡、抗贡、还贡真实换牌；还贡牌面2～10；手动进还贡与自动流程共用规则。
- 首局翻明牌确定起牌和首出，唯一编号区分同牌副本；后续局由贡牌规则确定首出。
- 接风修复：最后出牌者已走完、其余全过时由仍有手牌的队友领出，压牌后正常继续。

108 cards, full round-level consistency, independent advancement, actual tribute exchanges,
2–10 returns, heart-level protection, unique face-up opening deal and teammate lead transfer are implemented.

## 界面 / Interface

- GUI观察与人机模式；AI1人工、其他自动，轮到人工即等待；暂停、新局及关闭清理计时器。
- AI1下/AI2右/AI3上/AI4左，AI1一行27张；GUI隐藏他人手牌，viewer显示全部。
- 中央3:2分配，四框固定位置；只有当前玩家等待，其他保留上一手，显示游次与接风。
- 共用白底圆角牌面，花色在上点数在下，10字号增大，大小王为红/黑小丑图案，红心配和选牌高亮。
- PASS扩为三张牌宽后收紧白框高度。操作按钮多次调整为紧凑宽高、上方留白、Arial 12粗体金色。

Observer/human modes, stable timers, cross-shaped seating, hidden opponent hands, a 3:2 center split,
persistent action displays and finish ranks are complete. Shared card art includes larger tens and
colored jester artwork. PASS is wide but vertically compact; action buttons are compact gold bold text.

## 规则 AI / Rule AI

- 队友控牌默认让牌，直接走完及必要报单封堵例外；弱手送报单队友小散单。
- 第一轮领出改进取消固定顺子优先，按不重复用牌的贪心分组先处理弱小完整组。
- 保留炸弹/同花顺，一手可走完优先；对手报单时优先多张，日志解释每次规则选择。
- 未宣称策略已达到真人水平或已统计证明胜率改善；复杂百搭候选仍有限。

Partner yielding/feeding and blocking exceptions accompany greedy grouped leading, weak-group
priority, control-card retention and decision reasons. No measured strength improvement is claimed.

## LLM与平台 / LLM and platforms

- DeepSeek从合法动作编号中选择，后台请求，错误接管，日志区分模型与规则。
- 主界面“接入LLM”默认关闭，即时切换不重发牌；配置窗口只保存模型、座位和密钥。
- macOS钥匙串、Windows凭据管理器；密钥不入代码/日志；两系统分别保存设置。
- macOS可信CA补充，保留TLS校验；识别遮掩密钥，区分认证、余额、网络等失败。
- 设置窗口移除transient覆盖，新增关闭/Esc，保存成功自动关闭，保存期间可关闭。
- 用户已确认Windows和真实DeepSeek调用成功；本次整理回归仍仅在macOS自动执行。

DeepSeek action IDs, asynchronous fallbacks, opt-in switching, OS-native credential stores,
TLS and masked-key fixes, and reliable dialog closing are implemented. Windows and real API use
were user-confirmed; current automated validation runs locally on macOS.

## 本次整理 / This cleanup

- 重写两个README为中英双语，合并冲突的旧说明；完善规则、维护、状态与暂缓计划。
- 历史开发计划移入archive；保留红心配对比记录并标明历史性质。
- 删除无引用的根目录card/deck/identify旧原型、Finder剪辑和可再生缓存。
- 修正源码中的规则文档路径；安装元数据包含全部桌面模块；不改已有游戏行为。
- 250局统计窗口、两队不同模型、自动导出日志继续暂缓。

Both READMEs are bilingual; stale instructions are reconciled. Historical plans are archived,
unused prototypes and generated clutter removed, documentation references corrected and packaging
metadata expanded to include desktop modules. No new gameplay is introduced. Benchmarking,
multi-team LLM configuration and automatic exports remain deferred. See [cleanup record](docs/cleanup.md).

验证 / Validation：71项核心测试、四组桌面回归、文档链接与Python语法检查通过；
71 core tests, four desktop regressions, local documentation links and Python syntax passed.
