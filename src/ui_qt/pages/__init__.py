"""PyQt6 页面包。"""
from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget
from src.theme import Theme


class PageBase(QScrollArea):
    """可滚动的页面基类：统一边距 + 主题订阅。"""

    def __init__(self, state):
        super().__init__()
        self.setWidgetResizable(True)
        self.state = state
        self._t = state.theme
        self._inner = QWidget()
        self.setWidget(self._inner)
        self._lay = QVBoxLayout(self._inner)
        self._lay.setContentsMargins(28, 28, 28, 28)
        self._lay.setSpacing(16)
        self._build()
        state.subscribe(self._on_theme)

    def _build(self):
        """子类覆盖：构建页面控件树。"""
        raise NotImplementedError

    def _on_theme(self, theme: Theme):
        self._t = theme
        self._rebuild()

    def _rebuild(self):
        """换肤时重建（彻底清空 layout 后重新 _build）。
        
        必须用 takeAt 而非 itemAt——itemAt 只查看不删除，旧项会残留在布局中，
        导致每换一次主题就增加一层空白与 Layout 警告。
        """
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
            # spacer / stretch 无需额外处理，takeAt 已将其移除
        self._build()
        try:
            self.refresh()
        except Exception:
            pass  # 避免刷新过程中的异常影响主题切换

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def refresh(self):
        """子类覆盖：从 DAO 加载最新数据。"""
        pass
