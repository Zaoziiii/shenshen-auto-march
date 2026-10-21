"""BlueStacks 快速触摸：开一条 adb exec-in 通道，直接往虚拟触摸设备 /dev/input/event2 写原始事件。
不经过 `input` 命令（它在手指按住时每个点要等游戏处理完，约 18ms/点），节奏由电脑这边控制。
坐标是安卓像素（1080×1920 基准由 adbin.px 负责换算）。"""
import struct, subprocess, time

ADB = '/Applications/BlueStacks.app/Contents/MacOS/hd-adb'
SERIAL = '127.0.0.1:5555'
DEV = '/dev/input/event2'          # BlueStacks Virtual Touch：ABS_MT_POSITION 0..32767
EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
BTN_TOUCH, ABS_MT_X, ABS_MT_Y, ABS_MT_TRACKING_ID = 330, 53, 54, 57


def _ev(t, c, v):
    return struct.pack('<qqHHi', 0, 0, t, c, v)


class RawTouch:
    def __init__(self, w=1080, h=1920):
        self.w, self.h = w, h
        self.p = subprocess.Popen([ADB, '-s', SERIAL, 'exec-in', f'cat > {DEV}'], stdin=subprocess.PIPE)

    def _xy(self, x, y):
        return int(x * 32767 / self.w), int(y * 32767 / self.h)

    def _send(self, *evs):
        self.p.stdin.write(b''.join(evs) + _ev(EV_SYN, 0, 0))
        self.p.stdin.flush()

    def down(self, x, y):
        X, Y = self._xy(x, y)
        self._send(_ev(EV_ABS, ABS_MT_TRACKING_ID, 1), _ev(EV_KEY, BTN_TOUCH, 1),
                   _ev(EV_ABS, ABS_MT_X, X), _ev(EV_ABS, ABS_MT_Y, Y))

    def move(self, x, y):
        X, Y = self._xy(x, y)
        self._send(_ev(EV_ABS, ABS_MT_X, X), _ev(EV_ABS, ABS_MT_Y, Y))

    def up(self):
        self._send(_ev(EV_ABS, ABS_MT_TRACKING_ID, -1), _ev(EV_KEY, BTN_TOUCH, 0))

    def close(self):
        try:
            self.p.stdin.close(); self.p.wait(timeout=3)
        except Exception:
            self.p.kill()


def path(pts, step=30, dt=0.008, hold=0.05, first=0.03):
    """按下 → 沿 pts 每 step 像素一个点、每点间隔 dt 秒 → 松开（pts 为安卓像素）"""
    import math
    t = RawTouch()
    t.down(*pts[0]); time.sleep(first)
    cur = pts[0]
    for p in pts[1:]:
        n = max(1, int(math.dist(cur, p) / step))
        for k in range(1, n + 1):
            t.move(cur[0] + (p[0] - cur[0]) * k / n, cur[1] + (p[1] - cur[1]) * k / n)
            time.sleep(dt)
        cur = p
    time.sleep(hold)
    t.up(); time.sleep(0.02)
    t.close()
