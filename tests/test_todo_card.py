"""待办卡片回归测试（PyQt6 offscreen）。

覆盖两个修复点：
1. 更换背景生效：有背景图时卡片背景透明（由 paintEvent 自绘），避免全局
   QSS 的不透明底色覆盖背景图；无背景时保持纯色样式；background_path
   能通过 DAO 持久化。
2. 双击待办进入对应专注：_TodoCard.mouseDoubleClickEvent 触发
   page._start_focus(td)，并经 state.on_start_focus 关联到专注页 load_todo。
"""
import json
import os
import types

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtGui import QPixmap, QColor, QMouseEvent
from PyQt6.QtCore import Qt, QPointF, QEvent
from PyQt6.QtWidgets import QApplication

from src.database import dao
from src.ui_qt.pages.todo_page import _TodoCard


# 进程级唯一 QApplication，测试期间保活，避免控件被提前回收
_APP = QApplication.instance() or QApplication([])


def _make_td(**over):
    td = dict(
        id=1, title="背单词", status=0, type=0, duration=1500,
        group_id=None, timer_type=0, priority=0,
        habit_unit=None, habit_target=None, background_path=None,
    )
    td.update(over)
    return td


class _FakePage:
    """满足 _TodoCard 构建与交互所需的最小 page 替身。"""

    def __init__(self):
        self.group_dao = types.SimpleNamespace(list=lambda: [])
        self.started = []

    def _start_focus(self, td):
        self.started.append(td)


def _make_dbl_click_event(button=Qt.MouseButton.LeftButton):
    """构造一个真实的双击鼠标事件（offscreen 下可安全构造）。"""
    return QMouseEvent(
        QEvent.Type.MouseButtonDblClick, QPointF(0, 0), QPointF(0, 0),
        button, button, Qt.KeyboardModifier.NoModifier,
    )


def _write_temp_png(tmp_path, color=QColor(80, 160, 60)):
    pm = QPixmap(64, 64)
    pm.fill(color)
    fp = os.path.join(str(tmp_path), "bg.png")
    assert pm.save(fp, "PNG")
    return fp


# ---------------- 背景相关 ----------------

def test_card_without_background_uses_solid_style():
    page = _FakePage()
    card = _TodoCard(page, _make_td(), groups={})
    assert card._bg_pixmap is None
    # 无背景：面板使用纯色 background（surface 系）
    assert "background:transparent" not in card.styleSheet()
    assert "background:" in card.styleSheet()


def test_card_with_background_is_transparent_panel(tmp_path):
    """回归：有背景时面板必须透明，否则全局 QSS 底色会盖住背景图。"""
    fp = _write_temp_png(tmp_path)
    page = _FakePage()
    card = _TodoCard(page, _make_td(background_path=fp), groups={})
    assert card._bg_pixmap is not None
    assert not card._bg_pixmap.isNull()
    assert "background:transparent" in card.styleSheet()
    assert "border:none" in card.styleSheet()


def test_load_bg_pixmap_absolute_and_missing(tmp_path):
    fp = _write_temp_png(tmp_path)
    page = _FakePage()
    card = _TodoCard(page, _make_td(), groups={})
    # 绝对路径存在
    pm = card._load_bg_pixmap({"background_path": fp})
    assert pm is not None and not pm.isNull()
    # 路径缺失返回 None
    assert card._load_bg_pixmap({"background_path": None}) is None
    assert card._load_bg_pixmap(
        {"background_path": os.path.join(str(tmp_path), "not_exist.png")}) is None


# ---------------- 双击进入专注 ----------------

def test_double_click_enters_focus_with_todo(tmp_path):
    page = _FakePage()
    td = _make_td(id=42)
    card = _TodoCard(page, td, groups={})
    ev = _make_dbl_click_event(Qt.MouseButton.LeftButton)
    card.mouseDoubleClickEvent(ev)
    assert ev.isAccepted() is True
    assert len(page.started) == 1
    assert page.started[0]["id"] == 42


def test_double_click_ignores_right_button():
    page = _FakePage()
    card = _TodoCard(page, _make_td(), groups={})
    ev = _make_dbl_click_event(Qt.MouseButton.RightButton)
    card.mouseDoubleClickEvent(ev)
    assert page.started == []


# ---------------- 专注与待办关联（DAO 持久化 + 回调） ----------------

def test_background_path_persists_via_dao(db):
    """更换背景写入的 background_path 能正确持久化与读取。"""
    t = dao.TodoDAO(db)
    tid = t.create("看书", duration=1500)
    t.update(tid, background_path="assets/bg/reading.jpg")
    got = t.get(tid)
    assert got["background_path"] == "assets/bg/reading.jpg"
    t.delete(tid)


# ---------------- 设置项生效：不划完成线 ----------------

class _FakePageState:
    """满足 _TodoCard 读取设置所需的 state 替身。"""

    def __init__(self, settings=None):
        self.settings_dao = types.SimpleNamespace(
            get=lambda k, d=None: (settings or {}).get(k, d))
        self.on_start_focus = None
        self.navigate = lambda route: None


class _FakePageWN(_FakePage):
    def __init__(self, settings=None):
        super().__init__()
        self.state = _FakePageState(settings)


def _has_line_through(card):
    """检查卡片内是否有控件的样式含删除线（完成线在标题 QLabel 上）。"""
    from PyQt6.QtWidgets import QLabel
    return any("line-through" in w.styleSheet()
               for w in card.findChildren(QLabel))


def test_strikethrough_shown_by_default_when_done():
    page = _FakePageWN({})
    card = _TodoCard(page, _make_td(status=1), groups={})
    assert _has_line_through(card) is True


def test_no_strikethrough_hides_line_when_done():
    page = _FakePageWN({"no_strikethrough": "true"})
    card = _TodoCard(page, _make_td(status=1), groups={})
    assert _has_line_through(card) is False


# ---------------- 设置项生效：固定排序 / 搜索 ----------------

def _make_todo_page(settings=None, todos=None, groups=None):
    """构造不执行 __init__ 的 TodoPage（仅用于验证列表刷新逻辑）。"""
    from unittest.mock import MagicMock
    from PyQt6.QtWidgets import QVBoxLayout, QWidget
    from src.theme import get_current_theme
    from src.ui_qt.pages.todo_page import TodoPage

    store = dict(settings or {})

    class _SDAO:
        def get(self, k, d=None):
            return store.get(k, d)

        def set(self, k, v):
            store[k] = v

    page = TodoPage.__new__(TodoPage)
    page._t = get_current_theme()
    page.filter_status = 0
    page.filter_group = "all"
    page._search_text = ""
    page._settings_store = store

    sdao = _SDAO()
    tdao = MagicMock()
    tdao.list = lambda status=None, group_id=None: list(todos or [])
    gdao = MagicMock()
    gdao.list = lambda: list(groups or [])

    state = MagicMock()
    state.settings_dao = sdao
    state.todo_dao = tdao
    state.group_dao = gdao
    page.state = state
    page.todo_dao = tdao
    page.group_dao = gdao
    page.ed_search = MagicMock()
    # 用真实控件承载布局，便于 findChildren 递归查找卡片
    container = QWidget()
    page._list_widget = container
    page.list_lay = QVBoxLayout(container)
    return page


def _card_titles(page):
    from src.ui_qt.pages.todo_page import _TodoCard
    return [w.td["title"] for w in page._list_widget.findChildren(_TodoCard)]


def _visible_card_titles(page):
    from src.ui_qt.pages.todo_page import _TodoCard
    return [w.td["title"] for w in page._list_widget.findChildren(_TodoCard)
            if w.isVisible()]


def _todo_dict(tid, title, priority=0, group_id=None):
    return dict(id=tid, title=title, status=0, type=0, duration=1500,
                group_id=group_id, timer_type=0, priority=priority,
                sort_order=0, background_path=None)


def test_fixed_sort_orders_by_priority():
    todos = [_todo_dict(1, "A", 0), _todo_dict(2, "B", 2), _todo_dict(3, "C", 1)]
    page = _make_todo_page(settings={"fixed_sort": "true"}, todos=todos)
    page._refresh_list()
    assert _card_titles(page) == ["B", "C", "A"]


def test_fixed_sort_off_keeps_db_order():
    # 关闭时保持 DAO 返回的原始顺序（id 顺序）
    todos = [_todo_dict(1, "A", 0), _todo_dict(2, "B", 2), _todo_dict(3, "C", 1)]
    page = _make_todo_page(settings={"fixed_sort": "false"}, todos=todos)
    page._refresh_list()
    assert _card_titles(page) == ["A", "B", "C"]


def test_enable_search_shows_when_many_todos():
    todos = [_todo_dict(i, f"T{i}") for i in range(12)]
    page = _make_todo_page(settings={"enable_search": "true"}, todos=todos)
    page._refresh_list()
    page.ed_search.setVisible.assert_called_with(True)


def test_enable_search_hidden_when_few_todos():
    todos = [_todo_dict(i, f"T{i}") for i in range(3)]
    page = _make_todo_page(settings={"enable_search": "true"}, todos=todos)
    page._refresh_list()
    page.ed_search.setVisible.assert_called_with(False)


def test_search_filters_by_title():
    todos = [_todo_dict(1, "背单词"), _todo_dict(2, "跑步")]
    page = _make_todo_page(settings={"enable_search": "true"}, todos=todos)
    page._search_text = "背"
    page._refresh_list()
    assert _card_titles(page) == ["背单词"]


def test_start_focus_invokes_on_start_focus_callback():
    """_TodoCard 通过 page._start_focus → state.on_start_focus 关联待办。"""
    from src.ui_qt.pages.todo_page import TodoPage

    loaded = []

    class _StubState:
        def __init__(self):
            self.on_start_focus = lambda td: loaded.append(td)

        def navigate(self, route):
            pass

    # 直接构造一个仅含 state 的轻量对象来调用 _start_focus 逻辑
    page = TodoPage.__new__(TodoPage)
    page.state = _StubState()
    td = _make_td(id=7)
    page._start_focus(td)
    assert len(loaded) == 1 and loaded[0]["id"] == 7


# ---------------- 待办集分组折叠 + 展开记忆 ----------------

def test_grouped_renders_all_todos_with_headers():
    groups = [{"id": 1, "name": "工作"}, {"id": 2, "name": "生活"}]
    todos = [_todo_dict(1, "写代码", group_id=1),
              _todo_dict(2, "健身", group_id=2),
              _todo_dict(3, "杂事", group_id=None)]
    page = _make_todo_page(settings={"remember_list_expand": "true"},
                           todos=todos, groups=groups)
    page._refresh_list()
    page._list_widget.show()  # 使控件层级可见，isVisible 才能反映显隐标志
    # 所有待办都渲染出来（含未分类）
    assert set(_card_titles(page)) == {"写代码", "健身", "杂事"}
    # 默认全部展开：卡片均可见
    assert _visible_card_titles(page) == ["写代码", "健身", "杂事"]


def test_grouped_respects_saved_collapse_state():
    groups = [{"id": 1, "name": "工作"}]
    todos = [_todo_dict(1, "A", group_id=1), _todo_dict(2, "B", group_id=1)]
    settings = {"remember_list_expand": "true",
                "group_expand_state": json.dumps({"1": False})}
    page = _make_todo_page(settings=settings, todos=todos, groups=groups)
    page._refresh_list()
    page._list_widget.show()
    # 卡片仍在（折叠只是隐藏）
    assert set(_card_titles(page)) == {"A", "B"}
    # 但默认折叠：不可见
    assert _visible_card_titles(page) == []


def test_toggle_group_persists_when_remember_on():
    from PyQt6.QtWidgets import QVBoxLayout, QWidget
    from src.ui_qt.pages.todo_page import _GroupHeader
    page = _make_todo_page(settings={"remember_list_expand": "true"})
    container = QWidget()
    container.setLayout(QVBoxLayout())
    container.show()  # 使 isVisible 反映显隐标志，便于模拟"展开→折叠"
    header = _GroupHeader("工作", True, lambda: None)
    page._toggle_group(1, header, container)
    # 折叠后容器隐藏
    assert container.isVisible() is False
    # 状态已持久化
    saved = json.loads(page._settings_store["group_expand_state"])
    assert saved.get("1") is False


def test_toggle_group_no_persist_when_remember_off():
    from PyQt6.QtWidgets import QVBoxLayout, QWidget
    from src.ui_qt.pages.todo_page import _GroupHeader
    page = _make_todo_page(settings={"remember_list_expand": "false"})
    container = QWidget()
    container.setLayout(QVBoxLayout())
    container.show()
    header = _GroupHeader("工作", True, lambda: None)
    page._toggle_group(1, header, container)
    assert container.isVisible() is False
    # 关闭记忆时不写入
    assert "group_expand_state" not in page._settings_store


def test_specific_group_filter_renders_flat():
    """选定单个待办集时直接平铺，不折叠。"""
    groups = [{"id": 1, "name": "工作"}]
    todos = [_todo_dict(1, "A", group_id=1), _todo_dict(2, "B", group_id=1)]
    page = _make_todo_page(settings={}, todos=todos, groups=groups)
    page.filter_group = "1"
    page._refresh_list()
    page._list_widget.show()
    assert _visible_card_titles(page) == ["A", "B"]
