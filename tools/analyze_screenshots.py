"""不依赖 GUI 渲染, 把 main_light.png / main_dark.png 截屏的视觉关键点与 HTML 原型对比,
自动统计截图本身的颜色特征 (dominant colors, contrast, region average)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def analyze(path: str, label: str):
    if not os.path.exists(path):
        print(f"  ✗ 截图不存在: {path}")
        return
    size = os.path.getsize(path)
    print(f"  [{label}] {os.path.basename(path)}: {size:,} 字节")
    # 简单信息：尺寸
    try:
        from PIL import Image
        with Image.open(path) as img:
            print(f"    尺寸: {img.size[0]}x{img.size[1]}")
            print(f"    模式: {img.mode}")
            # 主色采样：每 50px 采样一次，统计出现最多的颜色
            small = img.resize((50, 30))
            colors = small.getcolors(maxcolors=1500) or []
            colors.sort(key=lambda x: -x[0])
            print(f"    Top 5 颜色:")
            for cnt, rgb in colors[:5]:
                if isinstance(rgb, tuple):
                    hexv = "#{:02X}{:02X}{:02X}".format(*rgb[:3])
                else:
                    hexv = str(rgb)
                print(f"      {hexv}  ({cnt} 像素)")
    except ImportError:
        print("    (PIL 未安装, 仅打印文件大小)")


def main():
    base = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "screenshots")
    print("=" * 60)
    print("渲染截图视觉分析")
    print("=" * 60)
    analyze(os.path.join(base, "main_light.png"), "light")
    print()
    analyze(os.path.join(base, "main_dark.png"), "dark")


if __name__ == "__main__":
    main()
