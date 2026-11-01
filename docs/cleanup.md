# 清理记录 / Cleanup record — 2026-10-04

## 2026-10-28 Windows 本机构建整理

检查确认源码内容与 `b4b79d6` 一致，现有 Git 差异仅为 Windows 文件模式变化。保留源码、测试、牌面资源、虚拟环境和历史构建记录，清理项目 Python 字节码缓存。
根目录保留 `gui.exe` 与 `SHA256SUMS.txt`，更新 `dist/SHA256SUMS.txt`，并将根目录生成文件加入 Git 忽略规则。
本机构建使用 Windows x64、Python 3.13.12、PyInstaller 6.19.0；84 项核心测试、五组桌面回归和 exe 窗口启动检查均通过。
exe SHA-256：`151ba1cd7f7432967ad52d3a9a597de7d60e963fd915c00fe7176bcb03c9a7d7`。

删除根目录三份未被当前项目引用的旧规则原型；唯一实现保留在 `game_engine/`。
旧 `deck.py` 缺少点数2，不能继续作为实现参考。删除只含文件名的 Finder 文本剪辑。
Removed unreferenced root prototypes; `game_engine/` remains authoritative. The old deck omitted twos.
The Finder clipping contained only a filename.

| 删除文件 / Removed file | SHA-256 before deletion |
|---|---|
| `card.py` | `8d82a9afb717888c178909715e7a5a835319a23415d0c1fde77da4a0cd3c3446` |
| `deck.py` | `ab096011ed5cc6051306705b2f1adb614d37ba4829c29270f02ccc2ebf5dfd70` |
| `identify.py` | `96926d05ca9f79b8f044e167c27d07eb0c048ef770423e731568d761d979981f` |
| `tests/test_match_runner.textClipping` | `3f877aed16a1627f0689fb4ebe5a2bde2eba93ff3fb1aa3fb416eea5da8339b4` |

同时删除项目内（不含 `.venv`）的 `__pycache__` 与 `.DS_Store`；这些是可重新生成的缓存。
Removed regenerable Python/Finder caches outside `.venv`.

保留虚拟环境、AGENTS.md、全部有效测试、参考图片、预览图和兼容LLM接口。
原开发计划移动到 `docs/archive/development_plan_v0.1.md`，未丢弃历史内容。
Preserved the environment, instructions, active tests, reference art, previews and legacy LLM APIs;
the historical development plan was moved rather than discarded. No user credentials were accessed.


## 2026-10-24 目录检查与发布整理 / Directory review

检查源码、测试、文档、牌面资源及打包目录。保留所有有效源码和新功能、`gui.spec`、虚拟环境、历史计划和原始参考图。
`build/` 包含 Windows 打包产物与历史测试失败记录，保留本地且继续由 Git 忽略；不将其当作当前发布包上传。
Removed only regenerable Python/Finder caches. Preserved source, tests, artwork, the virtual environment, packaging recipe and local Windows build evidence.

本次删除 27 个缓存文件，共 296,899 字节。删除前清单：

| 文件 / File | 字节 / Bytes | SHA-256 |
|---|---:|---|
| `__pycache__/benchmark.cpython-313.pyc` | 16432 | `83e77c3153eb780e87a4d0cf03e78657b8a7dcae8a471f7c30a8e8a9768f2e75` |
| `__pycache__/card_ui.cpython-313.pyc` | 13375 | `33883e6497a794d28c44330e6bbdd5b1993d26709ec27c8fb70f2c6a2464a184` |
| `__pycache__/game_series.cpython-313.pyc` | 6243 | `e128f1f6704ff6b27407da12193326d1c063a64fb5ed2bb6d3183759486291a9` |
| `__pycache__/gui.cpython-313.pyc` | 48032 | `bd85188de49e0e305bc6ff459ab3786fb8473f980b01f92f66116effba24f67a` |
| `__pycache__/llm_dialog.cpython-313.pyc` | 12600 | `8ab048c5b9e381ede0173a00fea197a04eab6bfcf7a89dae8ea53613c33ffd93` |
| `__pycache__/llm_settings.cpython-313.pyc` | 17639 | `6e7be3a39ba306c22f2e4f23e10b81b4a910f708b990eb97ea4a19e22fad4446` |
| `__pycache__/match_runner.cpython-313.pyc` | 23507 | `2ba89ce8971ac08c609e8290fe98523000d86d1106c37638ff67fd0b9fcc4f1f` |
| `__pycache__/play_display.cpython-313.pyc` | 3173 | `cdcf5e29a42062b41d84be0cad364056e573842698aec58be07607b23a53939f` |
| `__pycache__/turn_log.cpython-313.pyc` | 2333 | `4c1d11cd28c5bac01eaff9d0d32d6b25245e1b68eecc7afaaf10c3725baa6a5b` |
| `__pycache__/viewer.cpython-313.pyc` | 22549 | `264673a913d85002edbdb07d0ad56ef3b38f127ccd7d87f36403925861f392c9` |
| `agents/__pycache__/__init__.cpython-313.pyc` | 236 | `0fef6882bd11cd772b33ce67dae75b9e33bf837ddc2284d48530779ed1bcbd62` |
| `agents/__pycache__/base.cpython-313.pyc` | 3125 | `08a167c1ddbe6143c0706a9acc7480debe0536be5543c420e640ab1cbc0ae0ce` |
| `agents/__pycache__/deepseek_agent.cpython-313.pyc` | 7489 | `d829b6be2c34b486f8a5afa75784a301f2796a9b1080c3aad9d1c074eb4c161e` |
| `agents/__pycache__/llm_agent.cpython-313.pyc` | 7833 | `3b9ff692e6e3bae5940c39dc2a72e8ded00e88c69d04f1299610eddf7c2f942d` |
| `agents/__pycache__/llm_client.cpython-313.pyc` | 11803 | `4a8f9030143548be85316cc8b813f245054f877860465f692f8da4df4069f251` |
| `agents/__pycache__/rule_agent.cpython-313.pyc` | 18519 | `0d09a561656bd34ca0f94436a69f20eb6b02fd7ac084242a0f5c5b6f3b42a6ff` |
| `agents/__pycache__/strategy_planner.cpython-313.pyc` | 4565 | `5ed9d6931b9355317b2dff968f7e6bd405f31139f129c187387e4f6fc7af5e46` |
| `game_engine/__pycache__/__init__.cpython-313.pyc` | 491 | `3ad500c279fe2f49a3660e7dd584b65f056e2ffc461c6d47ab82d001d1534d41` |
| `game_engine/__pycache__/card.cpython-313.pyc` | 5391 | `6b24be17a03e137a46d593a6e89181981613f296fa2ef75f7a687a399719c4cc` |
| `game_engine/__pycache__/card_type.cpython-313.pyc` | 3686 | `16a99c8bd294def2f3dd23bc0d443fadff37fa4880bc34c0ac2f93b3df1db016` |
| `game_engine/__pycache__/comparator.cpython-313.pyc` | 3232 | `6d1c339dbc8586f58b6bb5d7de33e9faaa21309c482f07303ea6430945bd128d` |
| `game_engine/__pycache__/deck.cpython-313.pyc` | 4976 | `2004642183220e6fceed7163d59cca11742bcda154dea9d4bd7eb39d4838b8c9` |
| `game_engine/__pycache__/identify.cpython-313.pyc` | 14656 | `442d509b55f6065bbfcb0df0fe08790505f6b1bbcc8a75f2771c78e547b53729` |
| `game_engine/__pycache__/moves.cpython-313.pyc` | 17166 | `4e655cf896696b1a719a38db1f4f487f56361a60175ee7610a223b4bb73273d3` |
| `game_engine/__pycache__/round_result.cpython-313.pyc` | 2976 | `ba66d36835f9a7061a11c2a21d6cbba06c6a9d3e92436d6496cd3130c4ff619e` |
| `game_engine/__pycache__/tribute.cpython-313.pyc` | 14628 | `38bf1ece1148cf22fe836af3b261ecbc9cd6fc1bd038d7ab135fcb957311f87d` |
| `.DS_Store` | 10244 | `cdbecfa96c7e1e3895276303d1884e8d39a62533bc9532bc29b3680146292e92` |

验证：本机 macOS、项目 `.venv` Python 3.13.3，84项核心回归通过。未重新验证 Windows 可执行文件。


## 2026-10-28 发布整理 / Release cleanup

保留有效源码、测试、兼容接口、原始图片、历史计划、虚拟环境及旧 Windows 构建记录。仅删除下列可再生缓存；构建产物通过 Release 发布。

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| `.DS_Store` | 8196 | `5896e840f1d18d51ccfb22397489025e2bab21c8c9e8fc4ea1d65719ed4748c4` |
| `agents/__pycache__/strategy_planner.cpython-313.pyc` | 4565 | `5ed9d6931b9355317b2dff968f7e6bd405f31139f129c187387e4f6fc7af5e46` |
| `agents/__pycache__/base.cpython-313.pyc` | 3125 | `08a167c1ddbe6143c0706a9acc7480debe0536be5543c420e640ab1cbc0ae0ce` |
| `agents/__pycache__/llm_client.cpython-313.pyc` | 11803 | `4a8f9030143548be85316cc8b813f245054f877860465f692f8da4df4069f251` |
| `agents/__pycache__/rule_agent.cpython-313.pyc` | 18519 | `0d09a561656bd34ca0f94436a69f20eb6b02fd7ac084242a0f5c5b6f3b42a6ff` |
| `agents/__pycache__/__init__.cpython-313.pyc` | 236 | `0fef6882bd11cd772b33ce67dae75b9e33bf837ddc2284d48530779ed1bcbd62` |
| `agents/__pycache__/deepseek_agent.cpython-313.pyc` | 7489 | `d829b6be2c34b486f8a5afa75784a301f2796a9b1080c3aad9d1c074eb4c161e` |
| `__pycache__/match_runner.cpython-313.pyc` | 23507 | `2ba89ce8971ac08c609e8290fe98523000d86d1106c37638ff67fd0b9fcc4f1f` |
| `__pycache__/card_ui.cpython-313.pyc` | 13375 | `33883e6497a794d28c44330e6bbdd5b1993d26709ec27c8fb70f2c6a2464a184` |
| `__pycache__/llm_dialog.cpython-313.pyc` | 12600 | `8ab048c5b9e381ede0173a00fea197a04eab6bfcf7a89dae8ea53613c33ffd93` |
| `__pycache__/play_display.cpython-313.pyc` | 4404 | `c5f3540f1d438a6134f448d9f72b0a2c8fb13164e830722f12b20b10bbb151f8` |
| `__pycache__/game_series.cpython-313.pyc` | 6243 | `e128f1f6704ff6b27407da12193326d1c063a64fb5ed2bb6d3183759486291a9` |
| `__pycache__/turn_log.cpython-313.pyc` | 2333 | `4c1d11cd28c5bac01eaff9d0d32d6b25245e1b68eecc7afaaf10c3725baa6a5b` |
| `__pycache__/llm_settings.cpython-313.pyc` | 17639 | `6e7be3a39ba306c22f2e4f23e10b81b4a910f708b990eb97ea4a19e22fad4446` |
| `game_engine/__pycache__/deck.cpython-313.pyc` | 4976 | `2004642183220e6fceed7163d59cca11742bcda154dea9d4bd7eb39d4838b8c9` |
| `game_engine/__pycache__/identify.cpython-313.pyc` | 14619 | `36b01b4e65ba8960d79fafada03f16d3ca5d633a7c76ffbc8b7efe8ff12685b7` |
| `game_engine/__pycache__/moves.cpython-313.pyc` | 17149 | `fcd907137978d783dd27084e9077afdd15d788a049c3a322052ad2ae9da9363d` |
| `game_engine/__pycache__/round_result.cpython-313.pyc` | 2976 | `ba66d36835f9a7061a11c2a21d6cbba06c6a9d3e92436d6496cd3130c4ff619e` |
| `game_engine/__pycache__/comparator.cpython-313.pyc` | 3232 | `6d1c339dbc8586f58b6bb5d7de33e9faaa21309c482f07303ea6430945bd128d` |
| `game_engine/__pycache__/card_type.cpython-313.pyc` | 3686 | `53b542b02b74e398207187d765917faeb255635c404da5d8fd5929a4993518a2` |
| `game_engine/__pycache__/tribute.cpython-313.pyc` | 14628 | `38bf1ece1148cf22fe836af3b261ecbc9cd6fc1bd038d7ab135fcb957311f87d` |
| `game_engine/__pycache__/__init__.cpython-313.pyc` | 491 | `3ad500c279fe2f49a3660e7dd584b65f056e2ffc461c6d47ab82d001d1534d41` |
| `game_engine/__pycache__/card.cpython-313.pyc` | 5391 | `6b24be17a03e137a46d593a6e89181981613f296fa2ef75f7a687a399719c4cc` |

本次共删除23个缓存文件，201,182字节；macOS与Windows均通过84项核心和五组桌面回归。Windows exe 及校验文件已发布至 Release，本地副本在 `dist/`。


## 2026-10-30 本地修改检查与缓存清理

保留 LM Studio 客户端、设置窗口、GUI 接入、六项新增测试和使用说明；统一 `.gitignore` 换行，更新使用说明为当前项目运行指引。保留虚拟环境、资源、全部有效测试及 Windows 构建文件。既有 Windows 验证记录为历史记录，本次不重新确认其结论。

删除 25 个可再生缓存文件，共 220,268 字节：

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| `.DS_Store` | 10244 | `6e4d13532d5fe8f410a05242ac85f8d71fc1ef3de7c75e88781b9a960c617c06` |
| `agents/__pycache__/strategy_planner.cpython-313.pyc` | 4533 | `0015dcd45fc4b596f85b5b9497a221e7b1810b19e8c082e13b308edc3d8c6959` |
| `agents/__pycache__/base.cpython-313.pyc` | 3093 | `ab2b8ee7fe17dc8b25dc5bfae99f13e0b302eb2e58e3ac9040306390f9576841` |
| `agents/__pycache__/lmstudio_client.cpython-313.pyc` | 5560 | `6268c54eab217bdc6a192f1431140aee1af6d2865387fc71e5aaf76c7f62f6e6` |
| `agents/__pycache__/llm_client.cpython-313.pyc` | 11771 | `95a3bc92cede3b17a3038269004e70cd8cf15b61a229f64a50a99f92078a79bf` |
| `agents/__pycache__/rule_agent.cpython-313.pyc` | 18487 | `f08db4921c9d13119ca5aeab1cb5c233f369d2a2fb9061df1236b30e16ec10c3` |
| `agents/__pycache__/__init__.cpython-313.pyc` | 204 | `5327e60b48dadf5397d8ab691558ea1fa3a8ae8e82bdde2c9a7a35bf1f34fedc` |
| `agents/__pycache__/deepseek_agent.cpython-313.pyc` | 7596 | `27f6912f8e3a96a40854e01b87c5f8c51b665553b1606b748525759c0a19a4c6` |
| `__pycache__/match_runner.cpython-313.pyc` | 23475 | `7d6ca41a04fef8567604a7bf5aa251e75fbd34ca6e1e20597e64dd6b1de2192d` |
| `__pycache__/card_ui.cpython-313.pyc` | 13343 | `729d7335f11832b6ccf9b9202b5be5e89f714c9c597eb05c4a8eba5aff61dad8` |
| `__pycache__/llm_dialog.cpython-313.pyc` | 17025 | `dbc5b0040d759f77d7798c8be12057bb511baffe06cdbd7e8b6804dfc1ac9af3` |
| `__pycache__/play_display.cpython-313.pyc` | 4372 | `3eb01f2369a1de908dc70977a1db630a1555d6042156214a16a66f2937fc9792` |
| `__pycache__/game_series.cpython-313.pyc` | 6211 | `667740cb09bbf63ee4b3ce55df71b25b23873cc881f54199436d37da2a43f6d0` |
| `__pycache__/turn_log.cpython-313.pyc` | 2301 | `8e3c42e6f9b1b72ce80ee71b36c0e5937f0cecc7cbbe46dad4d7dc3f3e4a56fd` |
| `__pycache__/llm_settings.cpython-313.pyc` | 19045 | `6e46e4a46a7dd62d1d7dcedc4fc94e90b1e8848dc14bedde3cfd50be4f030b73` |
| `docs/.DS_Store` | 6148 | `d65165279105ca6773180500688df4bdc69a2c7b771752f0a46ef120b7fd8ec3` |
| `game_engine/__pycache__/deck.cpython-313.pyc` | 4944 | `25dd59186dd81ce51b9414c306e13b31454f3e57fc28a6b2f947c7b761daf456` |
| `game_engine/__pycache__/identify.cpython-313.pyc` | 14587 | `7b4375d0e90527f9c7f0bc2a80b63a474fc9c0be7f75606db03d142f5b4f52d5` |
| `game_engine/__pycache__/moves.cpython-313.pyc` | 17117 | `eab59c4d53fc19cc79f62abfa6b761b9a420000ec5942e916b9dd6c7fa51b61f` |
| `game_engine/__pycache__/round_result.cpython-313.pyc` | 2944 | `7ab11a228db45ee30f871d752920f48be5caf799f3123bb32dc94fcf8bc513d2` |
| `game_engine/__pycache__/comparator.cpython-313.pyc` | 3200 | `c79c9dcd6f20e1f6e9aabbe3225395de2273a75655c73a65de0305bb726f352c` |
| `game_engine/__pycache__/card_type.cpython-313.pyc` | 3654 | `a36ccba6614659821440d49c47c3cc73aef20b73f87627a89aa98b14a7bfe5e4` |
| `game_engine/__pycache__/tribute.cpython-313.pyc` | 14596 | `eeb69aa914cd53d938e29a1f330dcf41258aa212fa009e63d1b920e69a3d4fcf` |
| `game_engine/__pycache__/__init__.cpython-313.pyc` | 459 | `d25222277814962ded3a591187ac8410de8164eff25e70d4e05d37514683eae6` |
| `game_engine/__pycache__/card.cpython-313.pyc` | 5359 | `d0bee515e3477e8fce305b59a3254499160643a0083f2d01fea1c2dde8a7410b` |

本次验证：macOS 项目 `.venv/bin/python` 执行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/run_all.py`，90 项测试全部通过。LM Studio 测试使用模拟请求，未进行真实模型推理、Tk 窗口视觉验收或 Windows exe 验证。修改保留在工作区，未提交或推送。
