# 项目开发约定

## 扑克牌视觉

用户指定 guandan_ai 与 guandan_claude 使用同一套扑克牌画面。
参考图及规范：`assets/card_style/reference.png`、`assets/card_style/README.md`。
新增或修改图形界面中的牌面，复用 `card_ui.py`：白底黑色圆角边框，花色在上、衬线点数在下。
文本日志继续使用文字牌面。保持红心配和选牌的状态提示，不随意换成另一套牌面设计。
牌面组件独立于规则引擎；跨项目只同步视觉相关内容，并使用各项目实际环境验证。

## 代码分层

- `presentation/` 负责窗口、牌面、交互与显示；根目录 `gui.py`、`viewer.py`、`play.py`、`card_ui.py` 等保留为兼容入口。牌面正式实现位于 `presentation/cards.py`。
- `game_engine/` 负责牌型构成、张数、大小、红心配等合法性规则；不得依赖界面、策略、LLM 或对局协调层。候选排序或胜率偏好不得混入牌型合法性。
- `strategy/` 负责出牌选择和分组评估；只通过 `gameplay/contracts.py` 的 `Observation` / `Action` / `Agent` 契约连接对局，不依赖界面、LLM 客户端或完整对局对象。
- `gameplay/` 负责轮转、进还贡与升级协调；`integrations/llm/` 保留可选 LLM 适配；`evaluation/` 负责评测及经验案例。
- 新代码使用正式包路径，旧根目录模块和 `agents/` 仅做兼容，不复制实现。保持公共契约和兼容入口，改规则、界面或策略时分别验证，运行 `python tests/run_all.py` 的分层检查。
- 口诀和 LLM 决策先记录出处、适用局面及人工复核状态，再形成案例和策略改进；不得自动把模型输出当作最优策略或宣称棋力提高。
- 分层原则及修改指引见 `docs/architecture.md`，经验流程见 `docs/strategy_improvement.md`。
