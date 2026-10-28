# 维护说明 / Maintenance notes

## 实现入口 / Implementation boundaries

规则唯一来源为 `game_engine/`，根目录旧 `card.py/deck.py/identify.py` 原型已移除。
`Match.prepare()`幂等发牌和换牌；`Match._take_turn()`驱动AI，GUI人工入口通过同一动作校验。
`Observation`不含其他人的隐藏手牌。`DeepSeekAgent`使用合法动作编号；旧 `LLMAgent` 与
Coze客户端保留作兼容接口，不是当前GUI接入路径，也未作为已验证的Coze集成宣传。

`game_engine/` is authoritative. Match preparation is idempotent; human and AI actions use the same
validation. Observations exclude opponents' private cards. GUI uses `DeepSeekAgent` action IDs;
legacy `LLMAgent` and Coze adapters remain compatibility code, not a validated GUI integration.

## 界面与后台 / UI and background work

所有Tk修改在主线程；后台只处理请求与凭据，通过轮询交付结果。
暂停、关闭、新局、LLM切换使旧请求结果失效。请求可能仍在服务端执行并计费。
设置保存期间关闭窗口仍允许保存完成回调；不要重新引入 transient 强制覆盖父窗口。
统一牌面使用 `card_ui.py`；PASS专用显示在 `play_display.py`，不改共享牌面。

All Tk updates run on the main thread. Request generations invalidate stale replies; remote requests
may still be billed. Closing a settings window during saving preserves completion handling.
Do not reintroduce persistent parent-covering transient behavior. Shared card art and local PASS
presentation are separate modules.

## 验证 / Verification

- `python tests/run_all.py`：自动发现 `test_*.py`，标准库 unittest 执行。
- `gui_smoke.py`：牌桌、按钮、发牌和进贡；`gui_modes_smoke.py`：250步观察器一致性和完整人机比赛。
- `gui_llm_smoke.py`：假请求/假密钥，开关、保存关闭、过期回复与错误接管。
- `gui_play_status_smoke.py`：等待状态、保留出牌、PASS与游次。

Run the core suite and relevant desktop tests from the project root. GUI tests need a real desktop;
sandboxed Tk may fail for environmental reasons. No real key or paid request is needed for tests.
Windows credential tests simulate native boundaries; user-reported Windows success is distinct
from a new Windows validation. Do not copy virtual environments across operating systems.

## 文档与清理 / Documentation and cleanup

根README和牌面README均中英双语；CHANGELOG按功能归纳近期改动。
保留历史计划和百搭适配记录，当前规则说明以 `rules_design.md` 为准。
清理清单与删除前哈希见 [cleanup.md](cleanup.md)。不要清理用户系统凭据、运行环境或原始参考图。

Both READMEs are bilingual. Preserve historical plans and adaptation evidence; use current rules
for behavior. See [cleanup](cleanup.md) for removed files and hashes. Credentials, environments and
original reference artwork must not be treated as disposable project clutter.


## 2026-10-28 发布验证 / Release verification

macOS 项目 `.venv`：84 项核心测试及全部五组桌面回归通过，包括 250 步观察器一致性、7 小局完整人机比赛、模拟 LLM、出牌状态和统计窗口。修复小窗口下出牌尺寸约束挤压日志区的问题，恢复 3:2 比例。

Windows 发布流程见 `.github/workflows/windows-release.yml`：Python 3.13 x64、核心和五组桌面回归、PyInstaller 6.16.0、打包后窗口启动检查、SHA-256 及 Release 附件。构建日志是每次 Windows 验证的依据；自动检查不代表人工验收或真实付费 API 测试。
