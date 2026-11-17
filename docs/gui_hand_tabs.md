# GUI 手牌标签页（2026-11-16）

根目录 `gui.py` 仍为兼容入口。`presentation/hand_tabs.py` 负责 GUI / Play 标签页，复用 `presentation/table_view.py` 的手牌渲染扩展点；`presentation/play.py` 也复用同一组件，保持离线运行。

- 人机：同一行显示“你的手牌”、剩余/已选张数、“已出关键牌”、金框说明。切换标签不清除选牌。
- 观察：四个标签切换 S/E/N/W 的手牌，不显示“已出关键牌”，不可选牌。
- 已出关键牌：读取 `Match.played_cards`，依次为大王、小王、级牌、A、10、5；保留双副牌重复张数，红心配按印刷点数统计。级牌为 A/10/5 时，两列重复显示并注明。
- 牌面复用 `CardFace`，六列无水平叠放，各列垂直叠放，支持滚动条/滚轮。新对局重置标签，本轮统计随 Match 更换自然清零。

macOS 项目 `.venv/bin/python` 验证：

- `tests/run_all.py`：135 tests OK。
- `tests/gui_hand_tabs_smoke.py`：真实 Tk，通过四家手牌切换、人机专属关键牌标签、2/2/8/8/8/8 计数、级牌重合、选牌保留、滚动和新局清零。
- `tests/gui_smoke.py`：原有桌面牌桌/手牌布局、人机出牌、跨局进贡通过。
- 实际窗口截图已检查：`docs/evidence/gui-hand-tabs-observer.png`、`gui-hand-tabs-human.png`、`gui-hand-tabs-key-cards.png`。关键牌截图使用整副牌已出的显示夹具，不是真实对局状态。

本轮未验证 Windows、真实 LLM 或发布构建。

## Play 同步验证

`tests/gui_hand_tabs_smoke.py` 已同时覆盖 `GuandanGUI` 和 `GuandanPlay`，均通过。`tests/run_all.py` 135 tests OK。`tests/play_smoke.py` 通过：250 次观察动作与 viewer 一致，暂停/新局定时器正确；人机完成 12 轮，195 次出牌、119 次过牌、3 次进贡、4 次还贡。检查了 Play 关键牌实际窗口截图；未验证 Windows。截图 `docs/evidence/play-hand-tabs-key-cards.png` 使用整副牌已出显示夹具。
