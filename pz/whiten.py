"""连线时游戏会把「还能连到的同色泡泡」变成发白的淡色。
对比按下前后的截图，找出变白的泡泡位置（包括普通识别漏掉的）。"""
import cv2, numpy as np

Y0, Y1 = 470, 1150


def whitened(before, during):
    """返回变白泡泡的「眼睛坐标」列表 [(x, y), ...]（与 board.detect 的坐标约定一致）"""
    a = cv2.cvtColor(before, cv2.COLOR_BGR2HSV).astype(np.int16)
    b = cv2.cvtColor(during, cv2.COLOR_BGR2HSV).astype(np.int16)
    m = ((a[..., 1] - b[..., 1]) > 45) & (b[..., 2] > 170)
    m = m.astype(np.uint8) * 255
    m[:Y0] = 0; m[Y1:] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (35, 35)))
    # 白块不是实心的（眼睛、嘴巴不变白），按连通块取中心；太大的是已选链的连线特效
    n, _, st, cen = cv2.connectedComponentsWithStats(m)
    pts = [(int(cen[i][0]), int(cen[i][1])) for i in range(1, n) if 1500 <= st[i][4] <= 9000]
    return [(x, y - 15) for x, y in pts]   # 白块中心 ≈ 身体中心，眼睛在其上方约 15px


def whitened_same_color(before, during, bubbles, color, skip=()):
    """只看同色泡泡：身体饱和度明显下降（变成淡色）= 发白。返回发白泡泡（原元组）列表。
    比整屏做差稳得多：炸弹闪光、画面晃动都不会误判。"""
    a = cv2.cvtColor(before, cv2.COLOR_BGR2HSV).astype(np.int16)
    b = cv2.cvtColor(during, cv2.COLOR_BGR2HSV).astype(np.int16)
    out = []
    for p in bubbles:
        x, y, c = p[0], p[1], p[2]
        if c != color or any(abs(x - q[0]) < 30 and abs(y - q[1]) < 30 for q in skip):
            continue
        ys, xs = slice(y + 8, y + 42), slice(x - 22, x + 22)
        drop = (a[ys, xs, 1] - b[ys, xs, 1]).mean()
        if c == 'black':
            drop = (b[ys, xs, 2] - a[ys, xs, 2]).mean()      # 黑色泡泡发白 = 变亮
        # 发白主要在身体边缘和角（中间的眼睛、嘴不变）：整个泡泡里「淡白色像素」比按下前多了多少
        # 实测：发白的大多 >0.15；别的颜色被选中泡泡的光晃到偶尔 >0.06，所以取 0.10
        wr = lambda h: ((h[y - 30:y + 50, x - 40:x + 40, 1] < 100) & (h[y - 30:y + 50, x - 40:x + 40, 2] > 200)).mean()
        if drop > 12 or wr(b) - wr(a) > 0.10:          # 实测：发白的同色 14~22，不相关的 ≈0
            out.append(p)
    return out


HUE = {'red': [(0, 12), (160, 179)], 'yellow': [(13, 32)], 'green': [(36, 82)], 'blue': [(84, 120)], 'black': []}


def whitened_near_bombs(before, during, color, bombs, known, pad=110):
    """炸弹旁边的泡泡常被炸弹光挡住、普通识别认不出 → 在每个炸弹周围按颜色差找发白块。
    挖掉炸弹本身的圆，只要原来是该颜色、现在明显变淡的连通块。返回眼睛坐标 [(x, y)]"""
    if not bombs:
        return []
    a = cv2.cvtColor(before, cv2.COLOR_BGR2HSV).astype(np.int16)
    b = cv2.cvtColor(during, cv2.COLOR_BGR2HSV).astype(np.int16)
    hue = np.zeros(a.shape[:2], bool)
    for lo, hi in HUE[color]:
        hue |= (a[..., 0] >= lo) & (a[..., 0] <= hi)
    m = (((a[..., 1] - b[..., 1]) > 20) & (b[..., 2] > 170) & hue & (a[..., 1] > 100)).astype(np.uint8) * 255
    near = np.zeros_like(m)
    for x, y, lv, r in bombs:
        cv2.circle(near, (x, y), r + pad, 255, -1)
    for x, y, lv, r in bombs:
        cv2.circle(near, (x, y), r + 8, 0, -1)
    m = cv2.bitwise_and(m, near)
    m[:Y0] = 0; m[Y1:] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)))
    n, _, st, cen = cv2.connectedComponentsWithStats(m)
    out = []
    for i in range(1, n):
        if not 700 <= st[i][4] <= 9000:
            continue
        x, y = int(cen[i][0]), int(cen[i][1]) - 15
        if all(abs(x - k[0]) > 45 or abs(y - k[1]) > 45 for k in known + out):
            out.append((x, y))
    return out
