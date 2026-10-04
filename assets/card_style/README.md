# 统一扑克牌样式 / Shared card style

[中文](#中文) · [English](#english)

## 中文

用户指定 guandan_ai 与 guandan_claude 共用参考设计。`reference.png` 为完整保留的用户原图，
`preview.svg` 为设计预览。实际牌面由根目录 `card_ui.py` 绘制，不截取或拉伸参考图。

- 纵向牌，宽高约1:2；白底、细黑圆角边框。
- 上方居中大花色，下方居中粗衬线点数；A/K/Q/J不用人物插画，不用四角小标。
- 黑桃/梅花为 `#101010`；红心/方块为 `#c81018`。
- 10与单字符点数使用相同字号，避免过小。
- 红心配加金色外框，选牌加蓝色框并抬高，保留白底。
- 小王使用黑色星标，大王红色星标，并附“小王/大王”。王的设计为用户认可的补充，原图未包含。
- GUI中的PASS由 `play_display.py` 单独绘制：约三张牌宽，白框贴合粗体文字高度。
  PASS不是牌型，也不改变共享的54种牌面。

组件仅依赖Tkinter，不依赖规则引擎的Card/Suit/Rank类：

```python
from card_ui import CardFace, CardStrip
face = CardFace(parent, 'heart', 13)
face.pack()
strip = CardStrip(parent)
strip.pack(fill='both', expand=True)
strip.set_cards([('spade', 14), ('heart', 13), ('club', 12), ('diamond', 11)])
```

`suit`为spade/heart/club/diamond/joker；`rank`为2～16（11=J、14=A、15=小王、16=大王）。
采用相同构图和颜色，不保证与原图像素及字体轮廓完全一致。

历史接入包括本项目的GUI/viewer及guandan_claude的两个桌面入口。跨项目只同步牌面组件和必要调用点，
不覆盖游戏规则、进贡、升级或AI策略，并分别验证。本次文档整理未修改或重新验证另一项目。

## English

The user selected a shared design for guandan_ai and guandan_claude. `reference.png` preserves the
original artwork; `preview.svg` is a design preview. Runtime cards are drawn by root-level
`card_ui.py`, rather than cropped or stretched from the reference.

- Portrait cards, approximately 1:2 width/height, white fill and thin rounded black borders.
- Large centered suit above a bold serif rank; no court-card portraits or corner indices.
- Spades/clubs use `#101010`; hearts/diamonds use `#c81018`.
- Ten uses the same font size as single-character ranks.
- Heart wild cards have gold borders; selected cards have blue borders and are lifted, retaining white fill.
- Small joker: black star; big joker: red star, with Chinese joker labels. This is an approved addition
  because the original reference contains no jokers.
- GUI PASS is separately drawn by `play_display.py`, about three card widths with a white box fitted
  to the bold text height. It is a status marker, not an additional card type.

The Tkinter-only components are independent of engine Card/Suit/Rank classes. The example above
works in either project. Suits are spade/heart/club/diamond/joker; ranks are 2–16 (J=11, A=14,
small joker=15, big joker=16). Composition and colors follow the reference; exact pixels and font
outlines are not guaranteed.

The shared renderer was integrated into both desktop entrypoints in each project. Synchronize only
visual components and required callers, never game rules or AI strategy, and validate each target.
This documentation cleanup neither modifies nor revalidates guandan_claude.
