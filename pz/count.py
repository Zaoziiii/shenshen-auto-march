"""读连线计数：链旁边那个「白字 + 蓝色发光描边」的数字。
找到数字 → 白色笔画二值化、去掉杂点 → 放大后加个「N:」前缀让系统文字识别读；
读出来的数字顺便存成模板（pz/digits/），以后识别不了时用模板比对兜底。"""
import subprocess
from pathlib import Path
import cv2, numpy as np

ROOT = Path(__file__).parent.parent
DIG = Path(__file__).parent / 'digits'


def find_label(img, y0=440, y1=1160):
    h = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    white = ((h[..., 1] < 45) & (h[..., 2] > 240)).astype(np.uint8)
    blue = (((h[..., 0] >= 95) & (h[..., 0] <= 118)) & (h[..., 1] > 110) & (h[..., 2] > 170)).astype(np.uint8)
    m = (white & cv2.dilate(blue, np.ones((7, 7), np.uint8))) * 255
    m[:y0] = 0; m[y1:] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(m)
    cands = [(st[i][3], st[i][0], st[i][1], st[i][2]) for i in range(1, n)
             # 单个数字约 25×38（标准尺寸）；炸弹的白光块更大更宽，排除
             if 30 <= st[i][3] <= 50 and 8 <= st[i][2] <= 40 and 120 <= st[i][4] <= 1200
             and st[i][3] / st[i][2] >= 1.1 and st[i][4] / (st[i][2] * st[i][3]) < 0.7]
    if not cands:
        return None

    cands.sort(key=lambda c: -c[0])
    hh, x, y, w = cands[0]
    for h2, x2, y2, w2 in cands[1:]:   # 两位数：合并同一行挨着的块
        if abs(y2 - y) < 12 and abs(h2 - hh) < 12 and (abs(x2 - (x + w)) < 18 or abs(x - (x2 + w2)) < 18):
            nx = min(x, x2); w = max(x + w, x2 + w2) - nx; x = nx
    return x, y, w, hh


def _binarize(img, box):
    x, y, w, hh = box
    c = img[max(0, y - 2):y + hh + 2, max(0, x - 2):x + w + 2]
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV)
    ink = ((hsv[..., 1] < 60) & (hsv[..., 2] > 225)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink)
    keep = np.zeros_like(ink)
    for i in range(1, n):                      # 只留高度像数字笔画的块，去掉连线、杂点
        if st[i][3] >= 0.55 * hh:
            keep[lab == i] = 1
    return np.where(keep > 0, 0, 255).astype(np.uint8)


def _norm(bw):
    ys, xs = np.nonzero(bw < 128)
    if len(xs) == 0:
        return None
    c = bw[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return cv2.resize(255 - c, (24, 36), interpolation=cv2.INTER_AREA).astype(np.float32) / 255


def _vision(bw):
    big = cv2.GaussianBlur(cv2.resize(bw, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC), (5, 5), 0)
    big = cv2.copyMakeBorder(big, 80, 80, 200, 200, cv2.BORDER_CONSTANT, value=255)
    canvas = np.full((big.shape[0], big.shape[1] + 300), 255, np.uint8); canvas[:, 300:] = big
    cv2.putText(canvas, 'N:', (40, big.shape[0] // 2 + 40), cv2.FONT_HERSHEY_SIMPLEX, 4, 0, 12)
    p = ROOT / 'refs' / '_count.png'
    cv2.imwrite(str(p), canvas)
    out = subprocess.run([str(ROOT / 'ocr'), str(p)], capture_output=True, text=True).stdout
    txt = ''.join(' '.join(l.split(' ')[4:]) for l in out.splitlines())
    d = ''.join(ch for ch in txt if ch.isdigit())
    return int(d) if d else None


def _templates(bw):
    n = _norm(bw)
    if n is None or not DIG.exists():
        return None
    best = (0, None)
    for p in DIG.glob('*.png'):
        t = _norm(cv2.imread(str(p), 0))
        s = float((n * t).sum() / np.sqrt((n * n).sum() * (t * t).sum()))
        if s > best[0]:
            best = (s, int(p.stem.split('_')[0]))
    return best[1] if best[0] > 0.85 else None


def read_count(img):
    box = find_label(img)
    if not box:
        return None
    bw = _binarize(img, box)
    v = _vision(bw)
    if v is not None:
        DIG.mkdir(exist_ok=True)
        if len(list(DIG.glob(f'{v}_*.png'))) < 5:
            cv2.imwrite(str(DIG / f'{v}_{len(list(DIG.glob("*.png")))}.png'), bw)
        return v
    return _templates(bw)
