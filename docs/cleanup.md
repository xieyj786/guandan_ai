# 清理记录 / Cleanup record — 2026-10-04

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
