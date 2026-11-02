# 用真实经验持续改进打牌策略

目标是让规则 AI 会整理手牌、照顾队友、判断风险，逐步减少明显不合理的决策。
目录拆分只是让改进更安全；体验是否改善，仍要用具体牌例、对照比赛和真人试玩证明。

## 口诀不能直接变成无条件规则

每条经验记录：出处、原话、触发局面、选择、理由、例外和结果。例如“对手报单时不送小单”
仍需区分谁控牌、队友剩几张、是否能一手走完以及有没有更安全的组合。不能只把这句话
硬编码成永远出大单。`docs/guandan_strategy_analysis.md` 中已有的分析也应按适用条件复核。

建议流程：

1. 记录真实牌局或 LLM 决策，区分模型选择、规则回退与唯一合法动作；保存本局级牌、
   自己手牌、公开历史、上下家及队友剩余牌数、动作和结果。
2. 复盘具体局面，写出经验的适用条件和至少一个反例；未知结果保留 `unknown`。
3. 人工认可后，将有代表性的局面标为已复核案例；必要时记录多个可接受选择或拆为独立对照案例，
   不把单一动作匹配当作唯一的策略质量标准。
4. 在 `strategy/` 中实施有版本的策略修改，增加场景测试，检查合法性和旧经验退化。
5. 使用独立评测，固定种子、交换座位、覆盖 2 到 A、检查失败和模型回退。比较结果与决策耗时，
   再安排真人试玩，记录“明明有更好的牌却没出”“压队友”“拆好牌”等具体问题。

某局获胜不证明每一步最优；模型解释和一条口诀都需要验证。固定案例通过率与胜率分别报告。
遇到多种合理走法，应保留人工讨论或扩展可接受动作集合，不能为了逐字匹配损害实际配合。

## 已有代码接口

`evaluation/experience.py` 提供可直接使用的 JSONL 案例接口。调用者传入实际可见的
`Observation` 与实际 `Action`，不传完整 Match、客户端、API Key 或原始请求正文。

```python
from evaluation.experience import make_case, append_case, evaluate_cases
from strategy.rule_agent import RuleAgent

# observation 和 action 来自同一次决策；必须在后续动作修改牌局前构造案例。
case = make_case(
    'round-12-turn-7', observation, action,
    source='llm',                 # human / llm / rule
    decision_kind='llm',           # human / rule / llm / automatic / fallback
    strategy_version='candidate',
    reference='复盘记录编号/回合编号',
    note='记录触发条件、口诀、例外及复盘理由',
    outcome='unknown',             # unknown / win / loss
    approved=False,                # 默认仅为待复核素材
)
append_case('my_cases.jsonl', case)
results = evaluate_cases('my_cases.jsonl', RuleAgent)
```

`make_case()` 和读取接口验证动作是否属于规则允许的候选集合；实体手牌用编号保存，
两副相同牌不会混淆。文件只包含该玩家的观测、动作和案例标签，不包含对手底牌。
`approved=False` 的样本不参与偏好匹配；已复核样本报告 `agrees` 和 `legal`，不自动训练、
不改写 `strategy/`，不把匹配率当成胜率。

这是经验数据的基础接口，尚未自动从所有窗口采集，也没有把已有历史日志自动标注为正确答案。
未来接入采集时，在动作执行前复制本次观测并生成案例，避免异步请求返回后拿错回合；
模型回退必须标为 `fallback`，不能混算为模型能力。

现有 `benchmark_gui.py` / `evaluation/benchmark.py` 继续用于规则和 LLM 对照，保留配置、
逐局结果、事件和用量统计。旧日志可辅助复盘，但其字段不等于完整决策案例，不应凭空补成
可训练样本。真人经验和复盘完成后，再添加到专门的案例文件并纳入版本对比。

## 修改范围

策略迭代改 `strategy/rule_agent.py`、`strategy/planner.py` 及对应测试。只依赖自己手牌
和公开信息。体验改进需要解释具体为何更合理，不通过读取隐藏手牌取巧。
规则层只负责合法性；界面可以展示理由，但不自行决定哪手更优。
