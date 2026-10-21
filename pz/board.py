"""ぱずぎり 盘面识别：在 2x 截图里找出每个泡泡的位置和颜色（模板匹配，锚点 = 眼睛）。"""
from pathlib import Path
import cv2
import numpy as np

TPL_DIR = Path(__file__).parent / 'tpl'
BOARD = (440, 1130, 0, 708)    # y0, y1, x0, x1（2x 像素）
BOX = (32, 25, 45)             # 模板相对眼睛：左右各 32，上 25，下 45
THRESH = 0.55
MIN_DIST = 58                  # 两个泡泡眼睛之间的最小距离


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
    roi = img[y0:y1, x0:x1]
    w, up, dn = BOX
    cands = []
    for name, t in templates.items():
        res = cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.nonzero(res >= THRESH)
        for x, y in zip(xs, ys):
            parts = name.split('_')
            flame = len(parts) > 1 and parts[1].startswith('f')
            cands.append((float(res[y, x]), int(x + w + x0), int(y + up + y0), parts[0], flame))
    cands.sort(reverse=True)
    import flame
    kept = flame.detect(img)          # 火焰泡泡优先，普通模板不能覆盖它们
    for s, x, y, c, f in cands:
        if all((x - kx) ** 2 + (y - ky) ** 2 > MIN_DIST ** 2 for kx, ky, *_ in kept):
            kept.append((x, y, c, round(s, 2), f))
    return kept


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
