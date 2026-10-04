# 项目开发约定

## 扑克牌视觉

用户指定 guandan_ai 与 guandan_claude 使用同一套扑克牌画面。
参考图及规范：`assets/card_style/reference.png`、`assets/card_style/README.md`。
新增或修改图形界面中的牌面，复用 `card_ui.py`：白底黑色圆角边框，花色在上、衬线点数在下。
文本日志继续使用文字牌面。保持红心配和选牌的状态提示，不随意换成另一套牌面设计。
牌面组件独立于规则引擎；跨项目只同步视觉相关内容，并使用各项目实际环境验证。
