"""白噪音播放器（Windows 本地版，基于 winsound 循环播放）。

使用 Python 内置 winsound 模块播放 WAV 音频文件，原生支持循环播放。
非 Windows 平台优雅降级（仅提示，不发声）。

音频文件来源于 Wikimedia Commons、Mixkit 等免费资源，已预转换为 WAV 格式。
自定义上传的音频也会在上传时转换为 WAV，确保循环播放兼容性。
"""
import os
import platform
import sys

# winsound 是 Windows 专有模块，非 Windows 平台条件导入
try:
    import winsound
except ImportError:
    winsound = None


class WhiteNoisePlayer:
    """白噪音播放器：基于 winsound 的 WAV 文件循环播放。

    winsound.PlaySound 配合 SND_LOOP 标志可实现无缝循环，
    且为 Python 内置模块，无需额外依赖。
    仅支持 WAV 格式（自定义上传时自动转换）。
    """

    def __init__(self):
        self._playing_key: str | None = None
        self.available = platform.system() == "Windows" and winsound is not None

    # ---------------- 内部方法 ----------------
    @staticmethod
    def _resolve_path(path: str) -> str:
        """将相对路径解析为绝对路径。

        打包后（PyInstaller）：相对于 _MEIPASS（临时解压目录）
        开发环境：相对于项目根目录
        """
        if os.path.isabs(path):
            return path
        # PyInstaller 打包后的临时解压目录
        base = getattr(sys, '_MEIPASS', None)
        if base:
            return os.path.join(base, path)
        # 开发环境：src/audio_player.py 的上两级 = 项目根
        project_root = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        return os.path.join(project_root, path)

    # ---------------- 公开接口 ----------------
    def play_file(self, path: str) -> bool:
        """播放 WAV 音频文件（循环播放）。

        Args:
            path: 音频文件路径，支持相对路径（相对于项目根）和绝对路径。
                  仅支持 WAV 格式。

        Returns:
            True 表示播放成功。
        """
        if not self.available:
            print(f"[white-noise] 当前平台不支持音频播放（file={path}）")
            return False

        abs_path = self._resolve_path(path)
        if not os.path.exists(abs_path):
            print(f"[white-noise] 文件不存在：{abs_path}")
            return False

        ext = os.path.splitext(abs_path)[1].lower()
        if ext != ".wav":
            print(f"[white-noise] 仅支持 WAV 格式，当前文件为 {ext}：{abs_path}")
            return False

        try:
            self.stop()
            # SND_FILENAME: 从文件播放
            # SND_ASYNC:    异步播放，立即返回
            # SND_LOOP:     循环播放直到被停止
            winsound.PlaySound(
                abs_path,
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP,
            )
            self._playing_key = path
            return True
        except RuntimeError as ex:
            # PlaySound 可能抛出 RuntimeError: Failed to play sound
            print(f"[white-noise] 播放失败（可能文件格式不兼容）：{ex}")
            return False
        except Exception as ex:
            print(f"[white-noise] 播放文件失败：{ex}")
            return False

    def stop(self) -> None:
        """停止当前播放。"""
        if not self.available:
            return
        try:
            # PlaySound(None, 0) 停止所有异步播放
            winsound.PlaySound(None, 0)
        except Exception:
            pass
        self._playing_key = None

    @property
    def playing(self) -> str | None:
        """当前正在播放的文件路径（或 None）。"""
        return self._playing_key


_player = None


def get_player() -> WhiteNoisePlayer:
    """返回进程级单例播放器。

    避免专注页因切主题反复重建而创建多个播放器：winsound 的异步循环播放
    是进程级的，多个实例会导致旧声音无法被新实例停止、出现『关不掉』的
    孤儿播放。单例保证全局只有一个播放通道。
    """
    global _player
    if _player is None:
        _player = WhiteNoisePlayer()
    return _player
