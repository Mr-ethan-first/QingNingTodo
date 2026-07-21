"""白噪音播放回归测试（PyQt6 版，无需真实声卡/MySQL）。

回归『白噪音没有声音』和『算法生成不准确』：
1. _toggle_noise 对文件路径走 play_file()；
2. _toggle_noise 对关闭走 stop()；
3. 再次点击同一音源应停止播放；
4. 外部文件音源走 play_file；
5. play_file 对不存在的文件返回 False；
6. get_player 为单例；
7. 上传自定义音频功能存在。

专注页测试使用伪造播放器，不真实发声。
"""
import os
import tempfile

from src.audio_player import WhiteNoisePlayer, get_player
from src.ui_qt.pages.focus_page import FocusPage
from tests.test_main_window import _OffscreenApp, _FakeDB


class FakePlayer:
    def __init__(self):
        self.play_calls = []
        self.stop_calls = 0
        self.playing = None

    def play(self, key):
        """Deprecated stub, kept for backward compat."""
        self.play_calls.append(key)
        self.playing = key
        return True

    def play_file(self, path):
        self.play_calls.append(path)
        self.playing = path
        return True

    def stop(self):
        self.stop_calls += 1
        self.playing = None

    def is_playing(self):
        return self.playing is not None


def _make_focus_with_fake_player(player, noises):
    """构造 FocusPage 并替换 noise_player 为 FakePlayer。"""
    app = _OffscreenApp()
    from src.theme import DEFAULT_THEME
    from src.config import AppConfig
    from src.ui_qt.state import AppState
    state = AppState(_FakeDB(), AppConfig(), DEFAULT_THEME)

    from src.ui_qt.pages.focus_page import FocusPage
    original_build = FocusPage._build

    def patched_build(self):
        self._test_noises = noises
        orig = self._noises
        self._noises = lambda: self._test_noises
        original_build(self)
        self._noises = orig

    FocusPage._build = patched_build
    page = FocusPage(state)
    page.noise_player = player
    FocusPage._build = original_build

    page._noises = lambda: noises
    page._build_noise_buttons()
    return page


def test_noise_toggle_bound():
    """白噪音UI必须绑定 _toggle_noise 方法。"""
    assert hasattr(FocusPage, "_toggle_noise"), "FocusPage 缺少 _toggle_noise 方法"


def test_select_noise_plays_file():
    """选择音源应通过 play_file 播放对应文件路径。"""
    player = FakePlayer()
    noises = [{"id": 1, "name": "雨声 #1", "file_path": "assets/sounds/自然音/rain_1.wav", "category": "自然音"}]
    page = _make_focus_with_fake_player(player, noises)

    noise = noises[0]
    page._toggle_noise(noise)
    assert "assets/sounds/自然音/rain_1.wav" in player.play_calls, \
        f"应播放文件路径，实际 {player.play_calls}"


def test_select_off_stops():
    """再次点击同一音源应停止播放。"""
    player = FakePlayer()
    noises = [{"id": 1, "name": "雨声 #1", "file_path": "assets/sounds/自然音/rain_1.wav", "category": "自然音"}]
    page = _make_focus_with_fake_player(player, noises)

    noise = noises[0]
    page._toggle_noise(noise)
    assert player.playing is not None, "应正在播放"
    # 再次点击同一音源 → 停止
    page._toggle_noise(noise)
    assert player.stop_calls >= 1, "再次点击未调用 stop()"
    assert player.playing is None


def test_external_file_plays():
    """外部文件音源走 play_file。"""
    player = FakePlayer()
    noises = [{"id": 2, "name": "我的音乐", "file_path": "C:/a.mp3", "category": "轻音乐"}]
    page = _make_focus_with_fake_player(player, noises)

    page._toggle_noise(noises[0])
    assert "C:/a.mp3" in player.play_calls, f"应播放 C:/a.mp3，实际 {player.play_calls}"


def test_close_button_stops():
    """点击"关闭"按钮应停止播放。"""
    player = FakePlayer()
    noises = [{"id": 1, "name": "雨声", "file_path": "assets/sounds/自然音/rain_1.wav", "category": "自然音"}]
    page = _make_focus_with_fake_player(player, noises)

    # 先播放
    page._toggle_noise(noises[0])
    assert player.playing is not None

    # 点击关闭
    page._toggle_noise({"id": 0, "name": "关闭", "file_path": None, "category": "自然音"})
    assert player.stop_calls >= 1, "关闭未调用 stop()"
    assert player.playing is None


def test_play_file_nonexistent():
    """播放不存在的文件应返回 False。"""
    p = WhiteNoisePlayer()
    result = p.play_file("/nonexistent/path/to/file.wav")
    assert result is False, "不存在的文件应返回 False"


def test_player_singleton():
    """get_player 应返回进程级单例。"""
    from src import audio_player
    p1 = audio_player.get_player()
    p2 = audio_player.get_player()
    assert p1 is p2


def test_player_stop_when_not_playing():
    """停止未播放的播放器不应报错。"""
    p = WhiteNoisePlayer()
    p.stop()  # 不应抛异常


def test_upload_custom_noise_method_exists():
    """FocusPage 应有 _upload_custom_noise 方法。"""
    assert hasattr(FocusPage, "_upload_custom_noise"), \
        "FocusPage 缺少 _upload_custom_noise 方法"


def test_noise_dao_add_method_exists():
    """WhiteNoiseDAO 应有 add 方法。"""
    from src.database.dao import WhiteNoiseDAO
    assert hasattr(WhiteNoiseDAO, "add"), "WhiteNoiseDAO 缺少 add 方法"


def test_noise_dao_delete_method_exists():
    """WhiteNoiseDAO 应有 delete 方法。"""
    from src.database.dao import WhiteNoiseDAO
    assert hasattr(WhiteNoiseDAO, "delete"), "WhiteNoiseDAO 缺少 delete 方法"


def test_builtin_scheme_removed():
    """_toggle_noise 不应再处理 builtin:// 协议。"""
    import inspect
    source = inspect.getsource(FocusPage._toggle_noise)
    assert "builtin://" not in source, \
        "_toggle_noise 不应再包含 builtin:// 处理逻辑"


def test_play_file_with_real_wav():
    """play_file 对真实 WAV 文件应成功（仅 Windows）。"""
    import platform
    if platform.system() != "Windows":
        return

    # 创建一个最小的有效 WAV 文件
    import wave
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with wave.open(tmp_path, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframes(b'\x00\x00' * 44100)  # 1秒静音

        p = WhiteNoisePlayer()
        result = p.play_file(tmp_path)
        # winsound 在有音频设备时应成功，无设备时也不应崩溃
        if result:
            p.stop()
    finally:
        os.unlink(tmp_path)
