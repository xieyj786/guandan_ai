# 统一扑克牌样式 / Shared card style

[中文](#中文) · [English](#english)

## 中文

桌面版从 `svg/` 直接加载 54 张独立牌面，在 Tk 显示时按所需大小渲染并缓存。`reference.png`、旧总览和旧图集可用于历史对照。

- 普通牌画布为 250×400，大小王为 360×480。桌面显示统一使用普通牌的宽高比，大小王按同一牌框缩放。
- 普通牌的牌点右侧和下方各有同花色小标志。2～10 和 A 使用偏右下方的单个大花色。
- J/Q/K 使用单幅正向彩色人物。大小王使用彩色半身小丑、左侧竖排 JOKER 和两角星形。
- SVG 不包含位图或外部字体。红心配、选牌、末手描边及 PASS 由界面绘制。

组件依赖 Tkinter、Pillow 和 resvg-py，不依赖规则引擎的Card/Suit/Rank类：

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

The desktop app loads the 54 standalone cards from `svg/` and caches images rendered at the sizes Tk needs. The older atlas and previews are retained for reference.

Regular cards use a 250×400 viewBox. Jokers use 360×480. The desktop renderer fits jokers to the same width and height as regular cards. Regular cards show matching suit marks to the right of and below the rank. Number cards and aces have one large suit mark. J, Q, and K show one upright portrait. Each joker shows a colour jester bust, vertical JOKER lettering, and two stars.

The card component uses Tkinter, Pillow, and resvg-py. The example above
works in either project. Suits are spade/heart/club/diamond/joker; ranks are 2–16 (J=11, A=14,
small joker=15, big joker=16). Composition and colors follow the reference; exact pixels and font
outlines are not guaranteed.

The shared renderer was integrated into both desktop entrypoints in each project. Synchronize only
visual components and required callers, never game rules or AI strategy, and validate each target.
This documentation cleanup neither modifies nor revalidates guandan_claude.
