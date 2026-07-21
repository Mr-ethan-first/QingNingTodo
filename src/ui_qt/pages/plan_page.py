"""未来计划表页面（PyQt6）。"""
import datetime

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QMessageBox, QToolButton, QVBoxLayout

from src.ui_qt.dialogs import PlanDialog
from src.ui_qt.icons import icon
from src.ui_qt.pages import PageBase
from src.ui_qt.widgets import (
    badge, hero_banner, primary_button, section_title,
)


class PlanPage(PageBase):
    def __init__(self, state):
        self.plan_dao = state.plan_dao
        super().__init__(state)

    def _build(self):
        t = self._t
        header = QHBoxLayout()
        header.addWidget(section_title("未来计划表", "map"))
        header.addStretch(1)
        header.addWidget(primary_button("新建计划", icon_name="plus",
                                         on_click=self._add_plan))
        self._lay.addLayout(header)
        self._lay.addWidget(hero_banner("奔赴山海之约", "重要之事，铭刻于心"))

        tip = QLabel("记录重要事项的日期与倒计时，事项过期后不会消失，作为纪念保留。")
        tip.setStyleSheet(
            f"font-size:13px; color:{t.text_muted}; padding:0; margin:0;")
        self._lay.addWidget(tip)

        self.list_card = QFrame()
        self.list_card.setObjectName("card")
        self.list_lay = QVBoxLayout(self.list_card)
        self.list_lay.setContentsMargins(18, 18, 18, 18)
        self.list_lay.setSpacing(10)
        self._lay.addWidget(self.list_card)
        self._lay.addStretch(1)

    def refresh(self):
        self._rebuild_list()

    def _rebuild_list(self):
        while self.list_lay.count():
            item = self.list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        today = datetime.date.today()
        for p in self.plan_dao.list():
            self.list_lay.addWidget(self._plan_row(p, today))

    def _plan_row(self, p, today):
        t = self._t
        target = p["target_date"]
        if isinstance(target, str):
            try:
                target = datetime.date.fromisoformat(target)
            except Exception:
                target = today
        days = (target - today).days
        if days > 0:
            cd = f"还有 {days} 天"
        elif days == 0:
            cd = "就是今天！"
        else:
            cd = f"已过去 {abs(days)} 天"

        title = QLabel(p["title"])
        title.setStyleSheet(f"font-size:15px; font-weight:600; color:{t.text};")

        sub = QHBoxLayout()
        sub.setSpacing(8)
        sub.addWidget(badge(str(p["target_date"])))
        cd_lab = QLabel(cd)
        cd_lab.setStyleSheet(f"font-size:12px; font-weight:600; color:{t.primary};")
        sub.addWidget(cd_lab)
        if p.get("remark"):
            rm = QLabel(p["remark"])
            rm.setObjectName("subtle")
            sub.addWidget(rm)
        sub.addStretch(1)

        btn = QToolButton()
        btn.setIcon(icon("more", t.text_muted, 20))
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        # 隐藏QToolButton自带的下拉箭头，避免与三点图标重叠（与待办清单列表样式一致）
        btn.setStyleSheet(
            f"QToolButton{{border:none; border-radius:6px; background:transparent;}}"
            f"QToolButton:hover{{background:{t.surface};}}"
            f"QToolButton::menu-indicator{{image:none; width:0px;}}")
        menu = QMenu(btn)
        menu.setStyleSheet(
            f"QMenu{{background:{t.surface}; border:1px solid {t.border}; "
            f"border-radius:{t.radius_md}px; padding:6px 4px;}}"
            f"QMenu::item{{padding:8px 20px; border-radius:{t.radius_sm}px; "
            f"font-size:13px;}}"
            f"QMenu::item:selected{{background:{t.primary_soft}; color:{t.text};}}")
        menu.addAction(icon("edit", t.text_muted, 16), "编辑", lambda x=p: self._edit_plan(x))
        menu.addAction(icon("trash", t.text_muted, 16), "删除", lambda x=p: self._del_plan(x))
        btn.setMenu(menu)

        tick = QFrame()
        tick.setFixedSize(4, 38)
        tick.setStyleSheet(f"background:{t.accent2}; border-radius:999px;")

        row = QHBoxLayout()
        row.addWidget(tick)
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(title)
        col.addLayout(sub)
        row.addLayout(col, 1)
        row.addWidget(btn)

        card = QFrame()
        card.setObjectName("panel")
        card.setStyleSheet(
            f"#panel{{background:{t.surface_variant}; border:1px solid {t.border};"
            f" border-radius:{t.radius_md}px;}}")
        c_lay = QHBoxLayout(card)
        c_lay.setContentsMargins(12, 10, 12, 10)
        c_lay.addLayout(row)
        return card

    def _add_plan(self):
        dlg = PlanDialog(self.state, None, self)
        dlg.on_saved = self.refresh
        dlg.exec()

    def _edit_plan(self, p):
        dlg = PlanDialog(self.state, p, self)
        dlg.on_saved = self.refresh
        dlg.exec()

    def _del_plan(self, p):
        r = QMessageBox.question(self, "删除计划",
                                 f"确认删除『{p['title']}』？",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.plan_dao.delete(p["id"])
            self.refresh()
