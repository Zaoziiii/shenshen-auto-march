"""炸弹识别：棋盘里「没被认成泡泡」的大块区域 = 炸弹。
误把漏认的普通泡泡当成炸弹也没关系：单点一下普通泡泡不算出手。
等级按外圈光的颜色：蓝=1 绿=2 粉=3 白=4（4 级会自动爆）。"""
import cv2, numpy as np

LV = {'blue': 1, 'green': 2, 'pink': 3, 'white': 4}


_CACHE = {}


def _key(img, bubbles):
    return id(img), int(img[::97, ::89].sum()), len(bubbles)


def detect(img, bubbles):
    """同一张图、同一组泡泡一回合里会被问好几次（腾地方 / 火焰 / 合成方向 / 连线），算一次就缓存"""
    k = _key(img, bubbles)
    if k not in _CACHE:
        if len(_CACHE) > 8:
            _CACHE.clear()
        _CACHE[k] = _detect(img, bubbles)
    return list(_CACHE[k])


def _detect(img, bubbles):
    H, W = img.shape[:2]
    if len(bubbles) < 8:
        return []
    occ = np.zeros((H, W), np.uint8)
    for x, y, *_ in bubbles:
        cv2.circle(occ, (x, y + 15), 46, 255, -1)
    pts = np.array([(x, y + 15) for x, y, *_ in bubbles], np.int32)
    hull = np.zeros((H, W), np.uint8)
    cv2.fillConvexPoly(hull, cv2.convexHull(pts), 255)
    hull = cv2.dilate(hull, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (111, 111)))
    top = int(pts[:, 1].min()) + 20          # 最上排泡泡以上是敌人区域，不找炸弹
    hull[:max(470, top)] = 0; hull[1150:] = 0
    res = cv2.bitwise_and(hull, cv2.bitwise_not(occ))
    res = cv2.morphologyEx(res, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (45, 45)))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # 挨在一起的炸弹会连成一块：用距离变换的局部最大值拆成一个个圆心
    dist = cv2.distanceTransform(res, cv2.DIST_L2, 5)
    peak = (dist == cv2.dilate(dist, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (91, 91)))) & (dist >= 30)
    ys, xs = np.nonzero(peak)
    cands = sorted(zip(dist[ys, xs], xs, ys), reverse=True)
    centers = []
    for d, x, y in cands:
        if all((x - a) ** 2 + (y - b) ** 2 > (d + 25) ** 2 for a, b, _ in centers):
            centers.append((int(x), int(y), float(d)))
    import obstacles                         # 贝壳、箱子不是炸弹
    obst = obstacles.all_points(obstacles.detect(img))
    centers = [c for c in centers if all((c[0] - a) ** 2 + (c[1] - b) ** 2 > 55 ** 2 for a, b in obst)]
    out = []
    for x, y, d in centers:
        r = int(d)
        h = hsv[y - r:y + r, x - r:x + r, 0].ravel(); s = hsv[y - r:y + r, x - r:x + r, 1].ravel(); v = hsv[y - r:y + r, x - r:x + r, 2].ravel()
        bright = (v >= 235) & (s >= 30)
        hh = h[bright]
        vote = {'blue': ((hh >= 88) & (hh <= 115)).sum(), 'green': ((hh >= 38) & (hh <= 82)).sum(),
                'pink': ((hh >= 140) | (hh <= 6)).sum()}
        c = max(vote, key=vote.get)
        if vote[c] < 0.08 * len(h):
            if ((v >= 240) & (s < 30)).mean() > 0.3:
                c = 'white'
            else:
                continue
        out.append((x, y, LV[c], r))
    return out
