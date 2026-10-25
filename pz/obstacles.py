"""3-35 起出现的障碍物（用户）：
- 贝壳 shell：旁边消除后变成随机道具 → 规划时优先贴着贝壳连
- 箱子 box：旁边消除后变出 5 个黑色泡泡 → 规划时尽量别贴着箱子连
（箱子变出来的黑色泡泡是第 5 种颜色，可以连，在 board 里识别）
它们都不是泡泡，炸弹识别会把它们当成「没认出来的大块」，要排除。"""
import cv2, numpy as np
from pathlib import Path

TPL = {n: cv2.imread(str(Path(__file__).parent / 'tpl_obst' / f'{n}.png')) for n in ('shell', 'box')}
THRESH = {'shell': 0.66, 'box': 0.62}     # 会被旁边泡泡挡住一部分，阈值放低，再核对颜色


def _color_ok(n, img, x, y):
    h, s, v = [float(np.median(c)) for c in cv2.split(cv2.cvtColor(img[y - 10:y + 10, x - 10:x + 10], cv2.COLOR_BGR2HSV))]
    if n == 'shell':
        return s < 90 and v > 200                  # 淡粉白
    if n == 'box':
        return 8 <= h <= 25 and 60 <= s <= 200 and v > 150   # 竹编浅棕
    return False
NEAR = 105            # 泡泡中心(x, y+20) 到障碍物中心 ≤ 这个距离算「旁边」


_CACHE = {}


def detect(img):
    """返回 {名字: [(x, y), ...]}（障碍物中心，截图像素）。同一张图只算一次"""
    k = (id(img), int(img[::97, ::89].sum()))
    if k not in _CACHE:
        if len(_CACHE) > 8:
            _CACHE.clear()
        _CACHE[k] = _detect(img)
    return {n: list(v) for n, v in _CACHE[k].items()}


def _detect(img):
    area = img[450:1100]                  # 再往下是角色区，会误认
    out = {}
    for n, t in TPL.items():
        r = cv2.matchTemplate(area, t, cv2.TM_CCOEFF_NORMED)
        pts = []
        while True:
            _, v, _, (x, y) = cv2.minMaxLoc(r)
            if v < THRESH[n]:
                break
            cx, cy = x + t.shape[1] // 2, y + 450 + t.shape[0] // 2
            if _color_ok(n, img, cx, cy):
                pts.append((cx, cy))
            cv2.rectangle(r, (x - 40, y - 40), (x + 40, y + 40), -1, -1)
        out[n] = pts
    return out


def all_points(obst):
    return [p for v in obst.values() for p in v]


def touching(bubble, pts):
    x, y = bubble[0], bubble[1] + 20
    return sum(1 for a, b in pts if (a - x) ** 2 + (b - y) ** 2 <= NEAR ** 2)
