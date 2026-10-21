#!/usr/bin/env python3
"""BlueStacks 后台输入（adb）。坐标是 708×1562 标准截图坐标，这里换算成安卓像素。
用法:
  adbin.py tap x y
  adbin.py path x1 y1 x2 y2 ...     连线（中间插值，速度和 iPhone 版接近）
  adbin.py fast x1 y1 x2 y2 ...     乱舞横扫（插值更稀、不停顿）
也可以 import 后用 Session（按下 → 移动 → 截图 → 再移动 → 松开）。"""
import math, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ADB = '/Applications/BlueStacks.app/Contents/MacOS/hd-adb'
SERIAL = '127.0.0.1:5555'
STD_W, STD_H = 708, 1562


def _size():
    try:
        out = subprocess.run([ADB, '-s', SERIAL, 'shell', 'wm size'], capture_output=True, text=True, timeout=5).stdout
        w, h = out.strip().split(':')[-1].strip().split('x')
        return int(w), int(h)
    except Exception:
        return 1080, 2384


W, H = _size()


# iPhone 标准画面(708×1562) → BlueStacks 9:16 安卓画面(以 1080 宽为基准)：等比缩放 + 平移
# 用队伍页 6 个文字位置拟合（误差 ≤5px）：x' = 1.596x - 26, y' = 1.596y - 330
BS_K, BS_DX, BS_DY = 1.596, -26.0, -330.0


def px(x, y):
    f = W / 1080
    return int(round((x * BS_K + BS_DX) * f)), int(round((y * BS_K + BS_DY) * f))


def to_std_matrix(w):
    """安卓截图(w 宽) → iPhone 标准画面 的仿射矩阵（给 cv2.warpAffine）"""
    f = w / 1080
    k = 1 / (BS_K * f)
    return [[k, 0, -BS_DX / BS_K], [0, k, -BS_DY / BS_K]]


def _interp(pts, step):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.dist(a, b) / step))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1)]
    return out


def script(pts, step, pause, end_pause=0.15):
    """生成一条 shell 命令：DOWN → 一串 MOVE（每到一个原始点停 pause 秒）→ UP"""
    pts = [px(*p) for p in pts]
    cmds = [f'input motionevent DOWN {pts[0][0]} {pts[0][1]}', 'sleep 0.05']
    for a, b in zip(pts, pts[1:]):
        for x, y in _interp([a, b], step)[1:]:
            cmds.append(f'input motionevent MOVE {int(x)} {int(y)}')
        if pause:
            cmds.append(f'sleep {pause}')
    cmds += [f'sleep {end_pause}', f'input motionevent UP {pts[-1][0]} {pts[-1][1]}']
    return '; '.join(cmds)


def run(cmd):
    subprocess.run([ADB, '-s', SERIAL, 'shell', cmd], timeout=60)


class Session:
    """不松手的连续触摸（连线时中途截图看发白、再接着拖）——走原始触摸事件，速度和 iPhone 版相当"""
    def __init__(self):
        import rawtouch
        self.t = rawtouch.RawTouch(W, H)
        self.cur = None

    def down(self, x, y):
        self.cur = px(x, y)
        self.t.down(*self.cur)
        time.sleep(0.04)

    def _to(self, x, y, step, dt, pause):
        p = px(x, y)
        for a, b in _interp([self.cur, p], step)[1:]:
            self.t.move(a, b); time.sleep(dt)
        self.cur = p
        if pause:
            time.sleep(pause)

    def move(self, x, y):
        self._to(x, y, 24, 0.008, 0.03)          # 太快游戏会漏掉泡泡（第一遍经常断）

    def slow(self, x, y):
        self._to(x, y, 15, 0.015, 0.06)

    def up(self):
        time.sleep(0.08)
        self.t.up(); time.sleep(0.02)
        self.t.close()


if __name__ == '__main__':
    cmd, nums = sys.argv[1], [float(v) for v in sys.argv[2:]]
    pts = list(zip(nums[0::2], nums[1::2]))
    if cmd == 'tap':
        a, b = px(*pts[0])
        run(f'input tap {a} {b}')
    elif cmd in ('path', 'fast'):
        import rawtouch
        apts = [px(*p) for p in pts]
        if cmd == 'path':
            rawtouch.path(apts, step=30, dt=0.010, hold=0.12)    # 连线 / 拖地图
        else:
            rawtouch.path(apts, step=40, dt=0.006, hold=0.04)    # 乱舞横扫
