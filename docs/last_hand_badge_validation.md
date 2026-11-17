# 最后一手标签验证（2026-11-12）

桌面 gui.py、play.py 共用 presentation/play_display.py 的 PlayStrip 标签。仅 finish_order 中且仍有最后出牌的玩家显示“最后一手”，深绿色底、白字、细圆角边框，置于牌组上方。PASS、未出完玩家和新轮无标签；游次及最后出牌继续保留。

验证：临时 Python 环境运行 tests/run_all.py，134项全部通过；tests/gui_play_status_smoke.py 连续对局回归通过；tests/gui_last_hand_badge_smoke.py 检查两个兼容入口的真实Tk画布、标签文字、非出完座位无标记以及新局清除。已查看两个桌面窗口截图，Windows界面未实测。

效果图：evidence/last-hand-badge-gui.png、evidence/last-hand-badge-play.png。

桌面现有CRLF换行及其他修改保留。修改前备份：/private/tmp/guandan-last-hand-badge-backup-20261112-124301。

## 2026-11-12：文字标签改为座位同色边框

按用户要求同步SwiftUI方案：gui.py/play.py不再绘制“最后一手”文字标签，最后一手的每张牌采用2.5px圆角边框，直接读取对应座位的_team_color(team)，随领先队伍配色变化保持一致。红心配保留内侧金框，牌面图片尺寸及坐标不变。移除原标签预留空间，下一轮清除边框。

验证：tests/run_all.py的134项测试全部通过；tests/gui_last_hand_badge_smoke.py真实Tk验证两个兼容入口的边框颜色、红心配内外双框、牌面位置/大小不变、领先队伍变更后跟随座位色及新局清除；tests/gui_play_status_smoke.py连续对局显示回归通过。

已核对效果图：evidence/last-hand-border-gui.png、evidence/last-hand-border-play.png。macOS验证，不代表Windows界面已实测。现有其他修改和CRLF保留；修改前备份：/private/tmp/guandan-last-hand-border-backup-20261112-134052。
