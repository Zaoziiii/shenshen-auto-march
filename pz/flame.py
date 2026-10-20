"""紫色火焰泡泡：眼睛都是同样的粉色圆环 → 先找圆环，再看眼睛下方身体颜色判断是哪一色。"""
from pathlib import Path
import cv2, numpy as np

D = Path(__file__).parent / 'tpl_flame'
TH = 0.6
Y0, Y1 = 440, 1130


def detect(img):
    tpls = [cv2.imread(str(p)) for p in sorted(D.glob('*.png'))]
    roi = img[Y0:Y1]
    cands = []
    for t in tpls:
        h, w = t.shape[:2]
        res = cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.nonzero(res >= TH)
        cands += [(float(res[y, x]), int(x + w // 2), int(y + h // 2 + Y0)) for y, x in zip(ys, xs)]
    cands.sort(reverse=True)
    kept = []
    for s, x, y in cands:
        if all((x - a) ** 2 + (y - b) ** 2 > 52 ** 2 for a, b in kept):
            kept.append((x, y))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    out = []
    for x, y in kept:
        if y < 480 or purple_ratio(hsv, x, y) < 0.12:   # 排除「あと」倒数、炸弹脸
            continue
        c = body_color(hsv, x, y)
        if c:
            out.append((x, y, c, 1.0, True))
    return out


def body_color(hsv, x, y):
    """眼睛下方 18~46px、左右各 24px 的身体像素（排除紫色火焰、白色、暗部）"""
    r = hsv[y + 18:y + 46, x - 24:x + 24].reshape(-1, 3)
    r = r[(r[:, 1] > 90) & (r[:, 2] > 120) & ~((r[:, 0] >= 118) & (r[:, 0] <= 158))]
    if len(r) < 60:
        return None
    hh = r[:, 0]
    votes = {
        'red': ((hh <= 12) | (hh >= 159)).sum(),
        'yellow': ((hh >= 13) & (hh <= 32)).sum(),
        'green': ((hh >= 36) & (hh <= 80)).sum(),
        'blue': ((hh >= 84) & (hh <= 117)).sum(),
    }
    return max(votes, key=votes.get)


def purple_ratio(hsv, x, y):
    """火焰泡泡四周有紫色火焰（真火焰 ≥0.18，炸弹/倒数 <0.07）"""
    r = hsv[max(0, y - 45):y + 75, max(0, x - 62):x + 62]
    return (((r[..., 0] >= 118) & (r[..., 0] <= 158)) & (r[..., 1] > 100) & (r[..., 2] > 120)).mean()
