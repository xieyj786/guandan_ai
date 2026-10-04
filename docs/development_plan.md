# 当前状态与后续计划 / Status and roadmap

整理于2026-10-04。本阶段暂告一段，不在文档整理期间新增游戏功能。
Consolidated 2026-10-04. This milestone is paused; documentation cleanup adds no game features.

## 已完成 / Completed

- 108张牌、红心配识别、统一局级牌与双方独立升级。
- 首局翻明牌发牌、跨局进还贡/抗贡、接风、A级双下结束。
- GUI人机模式、观察模式、viewer、统一牌面、状态/PASS/游次、紧凑金色操作按钮。
- 规则AI第一轮弱小组合优先、保留控制牌、队友配合与可解释日志。
- DeepSeek合法动作编号、后台调用、异常接管、默认关闭的主界面开关。
- macOS钥匙串、Windows凭据管理器、TLS修复、密钥格式检查及可关闭设置窗口。

108-card rules, wild cards, round-wide levels, advancement, opening deals, tribute, lead transfer,
human/observer GUI, shared card art, rule heuristics/reasons, guarded asynchronous DeepSeek,
opt-in switch and native credentials on macOS/Windows are implemented.

## 待讨论或暂缓 / Pending or deferred

- 完善复杂红心配候选、跟牌与残局策略，使用具体复盘案例验证，不宣称胜率已提高。
- 多个LLM座位、两队分别配置不同服务商与密钥。
- 250局统计窗口与自动日志导出：用户明确暂缓，尚未开发。
- 统计方案草案：独立发牌、同牌交换策略、区分天然拥有与实际打出牌型、记录失败接管和用量。
  这些是讨论建议，不是已验收的规则或已实现功能。
- 搜索、强化学习、Web服务与断点复盘未实现。

Complex wildcard enumeration, follow/endgame strategy, multiple LLM seats/providers and evaluation
remain future work. The 250-round statistics window and automatic exports are explicitly deferred.
Paired deals, separate dealt/played card-type counts and fallback/usage reporting are proposals only.
Search, reinforcement learning, web services and resumable replays are not implemented.

早期计划原文保留在 [历史计划](archive/development_plan_v0.1.md)，其中的问题和范围不代表当前状态。
The [original plan](archive/development_plan_v0.1.md) is preserved as history, not current documentation.
