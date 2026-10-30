"""ぱずぎり 盘面识别：在 2x 截图里找出每个泡泡的位置和颜色（模板匹配，锚点 = 眼睛）。"""
from pathlib import Path
import cv2
import numpy as np

TPL_DIR = Path(__file__).parent / 'tpl'
BOARD = (440, 1130, 0, 708)    # y0, y1, x0, x1（2x 像素）
BOX = (32, 25, 45)             # 模板相对眼睛：左右各 32，上 25，下 45
THRESH = 0.55
MIN_DIST = 58                  # 两个泡泡眼睛之间的最小距离
# 活动关（BIG ト餓鬼）：泡泡有小（1 分）/ 中（3 分）/ 大（5 分）三种。设 SCALES 为多个缩放比例就按多尺寸识别，
# 每个泡泡的（身体缩放, 分值）记在 SIZE[(x, y)]。普通关 SCALES = (1.0,)，行为不变。
SCALES = (1.0,)
EVENT_SCALES = (1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7)
SIZE = {}
EYE_W = {'red': 27, 'blue': 30, 'green': 35, 'yellow': 24}   # 小泡泡眼白宽度（2026-10-31 实测）


def make_templates(img, eyes):
    """eyes: {name: (x, y)} 眼睛中心 → 存成模板"""
    TPL_DIR.mkdir(exist_ok=True)
    w, up, dn = BOX
    for name, (x, y) in eyes.items():
        cv2.imwrite(str(TPL_DIR / f'{name}.png'), img[y - up:y + dn, x - w:x + w])


def load_templates():
    return {p.stem: cv2.imread(str(p)) for p in sorted(TPL_DIR.glob('*.png'))}


def detect(img, templates=None):
    """返回 [(x, y, color, score, flame), ...]，(x, y) 为眼睛位置；
    模板名 'green_2' 归为 'green'，'red_f1' 归为 'red' 且 flame=True（紫色火焰泡泡）"""
    templates = templates or load_templates()
    y0, y1, x0, x1 = BOARD
    w, up, dn = BOX
    cands = []
    for sc in SCALES:
        im = img if sc == 1.0 else cv2.resize(img, None, fx=1 / sc, fy=1 / sc, interpolation=cv2.INTER_AREA)
        roi = im[int(y0 / sc):int(y1 / sc), int(x0 / sc):int(x1 / sc)]
        for name, t in templates.items():
            res = cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.nonzero(res >= THRESH)
            for x, y in zip(xs, ys):
                parts = name.split('_')
                flame = len(parts) > 1 and parts[1].startswith('f')
                cands.append((float(res[y, x]), int((x + w) * sc + x0), int((y + up) * sc + y0), parts[0], flame, sc))
    cands.sort(reverse=True)
    import flame
    kept = flame.detect(img)          # 火焰泡泡优先，普通模板不能覆盖它们
    scale = {(k[0], k[1]): 1.0 for k in kept}
    for s, x, y, c, f, sc in cands:
        if all((x - kx) ** 2 + (y - ky) ** 2 > (MIN_DIST * (sc + scale[(kx, ky)]) / 2) ** 2 for kx, ky, *_ in kept):
            kept.append((x, y, c, round(s, 2), f))
            scale[(x, y)] = sc
    if len(SCALES) > 1:
        SIZE.clear()
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        for x, y, c, *_ in kept:
            SIZE[(x, y)] = (scale[(x, y)], points(hsv, x, y, c, scale[(x, y)]))
    return kept


def points(hsv, x, y, c, sc):
    """活动关泡泡分值：看眼白宽度相对同色小泡泡的倍数（身体会被挤扁，眼睛不会）。
    实测倍数：小 ~1.0，中 1.33~1.45，大 1.55~1.67。量不到眼白时按身体缩放估。"""
    r = hsv[max(0, y - 35):y + 35, max(0, x - 35):x + 35]
    m = ((r[..., 1] < 50) & (r[..., 2] > 215)).astype(np.uint8)
    n, _, st, cen = cv2.connectedComponentsWithStats(m)
    cx, cy = min(x, 35), min(y, 35)
    best = min((((cen[i][0] - cx) ** 2 + (cen[i][1] - cy) ** 2, st[i][2]) for i in range(1, n) if st[i][4] > 30), default=None)
    if best and best[0] < 15 ** 2 and c in EYE_W:
        k = best[1] / EYE_W[c]
    else:
        k = 1.0 if sc < 1.1 else 1.4 if sc < 1.4 else 1.6
    return 1 if k < 1.17 else 3 if k < 1.5 else 5


def area(bubbles):
    """按普通泡泡折算的个数（活动关大泡泡占 ~2 个的地方）；普通关 = len"""
    return sum(size(p)[0] ** 2 for p in bubbles)


def size(p):
    """(身体缩放, 分值)；普通关一律 (1.0, 1)"""
    return SIZE.get((p[0], p[1]), (1.0, 1))


BGR = {'red': (0, 0, 255), 'yellow': (0, 220, 255), 'green': (0, 200, 0), 'blue': (255, 120, 0), 'black': (60, 60, 60)}


def draw(img, bubbles, path=None):
    vis = img.copy()
    for x, y, c, _, f in bubbles:
        cv2.circle(vis, (x, y + 12), 40, BGR.get(c, (255, 255, 255)), 4)
        if f:
            cv2.circle(vis, (x, y + 12), 48, (255, 0, 255), 3)
    if path:
        cv2.polylines(vis, [np.array([(b[0], b[1] + 12) for b in path])], False, (255, 0, 255), 8)
    return vis


if __name__ == '__main__':
    import sys
    img = cv2.imread(sys.argv[1])
    b = detect(img)
    from collections import Counter
    print(len(b), Counter(c for _, _, c, *_ in b), 'flame', sum(1 for *_, f in b if f))
    cv2.imwrite(sys.argv[2], draw(img, b))
