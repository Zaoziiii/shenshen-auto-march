"""不松手的连续触摸：按下 → 拖几个点 → 中途截图 → 再接着拖 → 松开。"""
import math, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def window_geom():
    """游戏画面区域：x, y, 宽, 高（屏幕点）。iPhone 镜像用 win，BlueStacks 用 winbs（PAZ_DEVICE）"""
    import os
    helper = 'winbs' if os.environ.get('PAZ_DEVICE') == 'bluestacks' else 'win'
    out = subprocess.run([str(ROOT / helper)], capture_output=True, text=True).stdout
    g = {}
    for line in out.splitlines():
        line = line.strip().rstrip(';').replace('"', '')
        for k in ('X', 'Y', 'Width', 'Height'):
            if line.startswith(k + ' ='):
                g[k] = float(line.split('=')[1])
    return g['X'], g['Y'], g.get('Width', 354), g.get('Height', 781)


def window_origin():
    return window_geom()[:2]


def to_screen(px, py):
    """708×1562 标准截图坐标 → 屏幕点"""
    x, y, w, h = window_geom()
    return x + px * w / 708, y + py * h / 1562


def Touch():
    """连续触摸会话：iPhone 镜像用鼠标（_MouseTouch），BlueStacks 用 adb（adbin.Session）"""
    import os
    if os.environ.get('PAZ_DEVICE') == 'bluestacks':
        sys.path.insert(0, str(ROOT))
        import adbin
        s = adbin.Session()
        _orig_up = s.up
        def up():
            _orig_up()
            import play
            play.mark()
        s.up = up
        return s
    return _MouseTouch()


class _MouseTouch:
    def __init__(self):
        subprocess.run([str(ROOT / 'g.sh'), 'focus'])
        self.ox, self.oy, w, h = window_geom()
        self.sx, self.sy = w / 708, h / 1562
        self.p = subprocess.Popen([str(ROOT / 'touch')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def _cmd(self, s):
        self.p.stdin.write(s + '\n'); self.p.stdin.flush(); self.p.stdout.readline()

    def _pt(self, px, py):           # 截图像素(2x) → 屏幕点
        return f'{self.ox + px * self.sx:.1f} {self.oy + py * self.sy:.1f}'

    def down(self, px, py): self._cmd('down ' + self._pt(px, py))
    def move(self, px, py): self._cmd('move ' + self._pt(px, py))
    def slow(self, px, py): self._cmd('slow ' + self._pt(px, py))

    def up(self):
        self._cmd('up'); self._cmd('quit'); self.p.wait()
        import play
        play.mark()
