"""单步/自动对战：截图 → 识别 → 选最长链 → 拖动。"""
import math, subprocess, sys, time
from pathlib import Path
import cv2, numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import board, solver, bombs, whiten, touch, count, obstacles

TEAM = []            # chars.identify() 的结果：3 个角色的奥义信息（farm 设置）
RESULT_IMGS = []     # 本局结算页截图（farm 读掉落用）


class Stopped(Exception):
    pass


LAST = None          # 脚本上一次操作结束时鼠标的位置


def cursor():
    try:
        return tuple(map(int, subprocess.run([str(ROOT / 'cursor')], capture_output=True, text=True).stdout.split()))
    except ValueError:
        return None


def mark():
    """每次脚本操作完记下鼠标位置；之后鼠标被人挪动了 = 用户要停"""
    global LAST
    LAST = cursor()


def check_stop():
    """紧急停止：App 里按 ⌃C（任何程序里都生效）或点停止按钮 → App 写 STOP 文件"""
    if (ROOT / 'STOP').exists():
        raise Stopped('收到停止（⌃C / 停止按钮）')


def bomb_level(n):
    return 3 if n >= 25 else 2 if n >= 14 else 1 if n >= 7 else 0


def orient_for_merge(b, ch, bb):
    """炸弹生成在链尾：如果反过来连能让新炸弹落在同级炸弹旁边（自动合成），就反过来"""
    import math
    lv = bomb_level(len(ch))
    if not lv or not bb or len(ch) < 2:
        return ch
    def near(i):
        x, y = b[i][0], b[i][1] + 15
        return any(l == lv and math.dist((x, y), (bx, by)) <= r + 70 for bx, by, l, r in bb)
    if not near(ch[-1]) and near(ch[0]):
        return ch[::-1]
    return ch


ROOT = Path(__file__).parent.parent
G = str(ROOT / 'g.sh')
SHOT = ROOT / 'refs' / '_live.png'


STD = (708, 1562)      # 所有识别坐标按这个尺寸写；窗口大小变了就把截图缩放到这个尺寸


def _bs_raw():
    """BlueStacks：adb 取未压缩的原始画面（0.2 秒；PNG 要 0.74 秒）"""
    out = subprocess.run(['/Applications/BlueStacks.app/Contents/MacOS/hd-adb', '-s', '127.0.0.1:5555',
                          'exec-out', 'screencap'], capture_output=True, timeout=10).stdout
    if len(out) < 16:
        return None
    w, h = int.from_bytes(out[0:4], 'little'), int.from_bytes(out[4:8], 'little')
    hdr = len(out) - w * h * 4                       # 头部 12 或 16 字节（新版多一个色彩空间字段）
    if hdr not in (12, 16):
        return None
    rgba = np.frombuffer(out, np.uint8, offset=hdr).reshape(h, w, 4)
    return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)


def _bs_reconnect():
    """adb 偶尔会掉线（BlueStacks 那边断开）：重新 connect 一下"""
    sys.path.insert(0, str(ROOT))
    import adbin
    try:
        subprocess.run([adbin.ADB, 'connect', adbin.SERIAL], capture_output=True, timeout=10)
    except subprocess.TimeoutExpired:
        pass


def shot():
    import os
    if os.environ.get('PAZ_DEVICE') == 'bluestacks':
        for _ in range(5):
            try:
                img = _bs_raw()
            except subprocess.TimeoutExpired:
                img = None
            if img is not None:
                sys.path.insert(0, str(ROOT))
                import adbin
                M = np.array(adbin.to_std_matrix(img.shape[1]), dtype=np.float32)
                return cv2.warpAffine(img, M, STD, flags=cv2.INTER_AREA, borderMode=cv2.BORDER_REPLICATE)
            time.sleep(1)
            _bs_reconnect()
        raise RuntimeError('截不到 BlueStacks 画面（adb 断开了？）')
    img = None
    for _ in range(5):                       # 截图偶尔失败（窗口刚变化等）→ 重试
        try:
            subprocess.run([G, 'shot', '_live'], timeout=10)
        except subprocess.TimeoutExpired:
            print(f'{time.time():.1f} 截图超时，重试', flush=True)
        img = cv2.imread(str(SHOT))
        if img is not None:
            break
        time.sleep(1)
    if img is None:
        raise RuntimeError('截不到 iPhone 镜像窗口（镜像断开了？）')
    import os
    if img is not None and os.environ.get('PAZ_DEVICE') == 'bluestacks':
        # BlueStacks 9:16 画面 → 换算成 iPhone 标准画面（上下超出部分用边缘像素延伸）
        sys.path.insert(0, str(ROOT))
        import adbin
        M = np.array(adbin.to_std_matrix(img.shape[1]), dtype=np.float32)
        return cv2.warpAffine(img, M, STD, flags=cv2.INTER_AREA, borderMode=cv2.BORDER_REPLICATE)
    if img is not None and (img.shape[1], img.shape[0]) != STD:
        img = cv2.resize(img, STD, interpolation=cv2.INTER_AREA)
    return img


def drag(pts):
    subprocess.run([G, 'drag', *[str(v) for p in pts for v in p]], check=True)
    mark()


def tap(x, y):
    subprocess.run([G, 'tap', str(x), str(y)], check=True)
    mark()


def same_layout(a, b, tol=12, miss=2):
    """两次识别基本一致：数量差 ≤miss，且最多 miss 个泡泡找不到同色近邻（待机晃动会让识别偶尔漏 1 个）"""
    if not a or abs(len(a) - len(b)) > miss:
        return False
    bad = sum(1 for x, y, c, *_ in a
              if not any(c == c2 and abs(x - x2) <= tol and abs(y - y2) <= tol for x2, y2, c2, *_ in b))
    return bad <= miss


def wait_stable(timeout=6):
    """等泡泡落定：连续两次识别结果一致就放行。
    不比较整张画面，因为泡泡待机晃动、炸弹火焰一直在动，像素永远不会完全静止。"""
    prev = shot(); pb = board.detect(prev); t = time.time()
    while time.time() - t < timeout:
        time.sleep(0.25)
        cur = shot(); cb = board.detect(cur)
        if same_layout(pb, cb):
            return cur
        prev, pb = cur, cb
    return prev


def step(save=None, prefer=()):
    img = wait_stable()
    b = board.detect(img)
    ch = solver.best_chain(b, prefer)
    path = [b[i] for i in ch]
    if save:
        cv2.imwrite(save, board.draw(img, b, path))
    if len(path) >= 2:
        drag([(x, y + 20) for x, y, *_ in path])
    return len(b), len(path), path[0][2] if path else None




# ---------- 自动对战 ----------
CHARS = [(150, 1215), (355, 1240), (570, 1215)]   # 3 个刀剑男士头像位置
LOG = ROOT / 'refs' / 'log'


def glow_center(img, x, y):
    """奥义光圈的中心（角色站位因队伍而异，固定坐标会点偏）"""
    r = cv2.cvtColor(img[y - 150:y + 90, x - 150:x + 150], cv2.COLOR_BGR2HSV)
    m = ((r[..., 0] >= 140) | (r[..., 0] <= 8)) & (r[..., 1] > 25) & (r[..., 1] < 120) & (r[..., 2] > 235)
    ys, xs = np.nonzero(m)
    if len(xs) < 200:
        return x, y
    return int(np.median(xs)) + x - 150, int(np.median(ys)) + y - 150


def pink_ratio(img, x, y):
    """奥义攒满时头像周围会出现粉色光圈"""
    r = cv2.cvtColor(img[y - 110:y + 90, x - 110:x + 110], cv2.COLOR_BGR2HSV)
    # 光圈是很亮的淡粉色（低饱和、高亮度）
    m = ((r[..., 0] >= 140) | (r[..., 0] <= 8)) & (r[..., 1] > 25) & (r[..., 1] < 120) & (r[..., 2] > 235)
    return m.mean()


SAKURA = [(90, 1262), (292, 1292), (500, 1262)]   # 三个角色左下角樱花（奥义需要的颜色）


def sakura_colors(img):
    """读每个角色樱花的底色 → ['blue', 'yellow', 'red'] 之类；读不出来的给 None"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    out = []
    for x, y in SAKURA:
        r = hsv[y - 28:y + 28, x - 28:x + 28].reshape(-1, 3)
        h = r[(r[:, 1] > 120) & (r[:, 2] > 120)][:, 0]
        votes = {'red': ((h <= 9) | (h >= 168)).sum(), 'yellow': ((h >= 10) & (h <= 30)).sum(),
                 'green': ((h >= 38) & (h <= 82)).sum(), 'blue': ((h >= 92) & (h <= 120)).sum()}
        c = max(votes, key=votes.get)
        out.append(c if votes[c] > 200 else None)
    return out


def is_aim_screen(img):
    """奥义选位置画面：四周有紫色边框"""
    r = cv2.cvtColor(img[400:1300, 20:60], cv2.COLOR_BGR2HSV)
    return (((r[..., 0] >= 125) & (r[..., 0] <= 160)) & (r[..., 1] > 80) & (r[..., 2] > 150)).mean() > 0.3


def is_rush(img):
    """乱舞时间：底部背景变成彩虹色"""
    r = cv2.cvtColor(img[1400:1500, 40:670], cv2.COLOR_BGR2HSV)
    if float(np.std(r[..., 0])) <= 35:
        return False
    # 还要有右上角紫色倒计时圆环（排除奥义特写动画：背景同样五颜六色）
    t = cv2.cvtColor(img[360:480, 520:650], cv2.COLOR_BGR2HSV)
    if (((t[..., 0] >= 130) & (t[..., 0] <= 165)) & (t[..., 1] > 120) & (t[..., 2] > 150)).mean() <= 0.2:
        return False
    # 3-35 的首领身上的紫光也在这个位置：再找倒计时的圆环（圆心约 (580, 421)，半径 ~57）
    g = cv2.medianBlur(cv2.cvtColor(img[340:500, 480:680], cv2.COLOR_BGR2GRAY), 5)
    c = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1.2, minDist=100, param1=100, param2=40, minRadius=40, maxRadius=62)
    return c is not None and any(abs(x + 480 - 580) < 18 and abs(y + 340 - 421) < 18 and r >= 50 for x, y, r in c[0])


def sweep_order(pts):
    import math
    cur = min(pts, key=lambda p: p[0] + p[1]); order = [cur]; rest = set(pts) - {cur}
    while rest:
        cur = min(rest, key=lambda p: math.dist(p, cur)); order.append(cur); rest.discard(cur)
    return order


def settle(max_wait=1.0):
    """乱舞中等泡泡落定：连续两次识别一致就返回（最多等 max_wait 秒，计时紧）"""
    img = shot(); b = board.detect(img); t = time.time()
    while time.time() - t < max_wait:
        img2 = shot(); b2 = board.detect(img2)
        if same_layout(b, b2):
            return img2, b2
        img, b = img2, b2
    return img, b


def _sweep_colors(img, b, keep, n, tag):
    """用同一次识别，把每种非保留色各扫一笔（数量多的先扫）"""
    groups = {}
    for x, y, c, *_ in b:
        if c != keep:
            groups.setdefault(c, []).append((x, y + 20))
    for k, (c, pts) in enumerate(sorted(groups.items(), key=lambda kv: -len(kv[1]))):
        order = sweep_order(pts)
        cv2.imwrite(str(LOG / f'rush_{n:03d}_{tag}{k}_{c}.png'), board.draw(img, b, [(x, y - 20, c, 0, False) for x, y in order]))
        subprocess.run([G, 'fast', *[str(v) for p in order for v in p]], check=True)
        print(f'{time.time():.1f}', n, f'rush {tag} {c} x{len(order)}', flush=True)
        time.sleep(0.05)
    return sum(len(v) for v in groups.values())


RUSH_WINDOW = 4.8     # 用户定：从第一次连接开始计时，超过这个秒数就不再快速连接


def _seg_dist(p, a, b):
    import math
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def safe_strokes(pts, avoid, clear=48):
    """乱舞用：把同色点分成若干笔，每一段线都不经过保留色泡泡（离它们 ≥clear px）。
    起点选离保留色最远的点；接不下去就断开另起一笔。"""
    import math
    rest = list(pts); strokes = []
    def far(p): return min((math.dist(p, a) for a in avoid), default=999)
    while rest:
        cur = max(rest, key=far); rest.remove(cur); s = [cur]
        while rest:
            ok = [q for q in rest if all(_seg_dist(a, cur, q) >= clear for a in avoid)]
            if not ok:
                break
            cur = min(ok, key=lambda q: math.dist(q, cur)); rest.remove(cur); s.append(cur)
        strokes.append(s)
    return strokes


RUSH_ORDER = ('yellow', 'blue', 'green')   # 乱舞扫色顺序（保留色跳过），循环直到倒计时结束
RUSH_X = (40, 668)                         # 横扫的左右边界（截图像素）
RUSH_TOP = 470                             # 扫到这里为止
RUSH_ROW = 85                              # 每一趟往上移多少（略小于泡泡直径 ~90，避免漏）


def zigzag_sweep(x0, y0):
    """用户定的乱舞扫法：按住起点（该颜色最下面的泡泡）→ 横着来回滑，一路往上扫到顶 → 松开。
    乱舞时只收集和第一个泡泡同色的，划过别的颜色没关系，所以不用识别位置。"""
    pts = [(x0, y0)]
    y = y0; go_right = x0 < (RUSH_X[0] + RUSH_X[1]) / 2
    while True:
        pts.append((RUSH_X[1] if go_right else RUSH_X[0], y))
        if y <= RUSH_TOP:
            break
        y = max(RUSH_TOP, y - RUSH_ROW)
        pts.append((pts[-1][0], y))
        go_right = not go_right
    import os
    if os.environ.get('PAZ_DEVICE') == 'bluestacks':
        sys.path.insert(0, str(ROOT))
        import adbin, rawtouch                       # 直接在本进程里写触摸事件，不再另开 python
        rawtouch.path([adbin.px(*p) for p in pts], step=55, dt=0.005, hold=0.04, first=0.15)
        mark(); return
    args = ['%.1f %.1f' % touch.to_screen(x, yy) for x, yy in pts]
    subprocess.run([str(ROOT / 'sweep'), '20', '5000', *' '.join(args).split()], check=True)
    mark()


HUE_OK = {'red': lambda h: h <= 12 or h >= 160, 'yellow': lambda h: 13 <= h <= 32,
          'green': lambda h: 36 <= h <= 82, 'blue': lambda h: 84 <= h <= 120, 'black': lambda h: True}


def stable_start(b, c, keep, img, strict=True):
    """乱舞起点：该色最下面的泡泡，离保留色 ≥55px；strict 时还要按下点颜色对得上
    （乱舞的彩色光效会让颜色偏移，所以颜色只在 strict 时检查）"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    cands = []
    for x, y, cc, *_ in b:
        if cc != c:
            continue
        if strict:
            hh = int(np.median(hsv[y + 12:y + 30, x - 10:x + 10, 0]))
            if not HUE_OK[c](hh):
                continue
        if any(ck == keep and math.dist((x, y), (xk, yk)) < 55 for xk, yk, ck, *_ in b):
            continue
        cands.append((y, x))
    if not cands:
        return None
    y, x = max(cands)
    return x, y


def rush_phase(keep, n, img=None):
    """乱舞时间（用户定）：先等泡泡停稳（第一次划才开始计时）→ 不限时，一直循环到退出乱舞：
    每一笔选「除保留色外当前最多的颜色」，找它最下面的一个，从它开始横向来回扫到顶部。"""
    img, b = settle(max_wait=1.2)
    if not is_rush(img):
        return
    subprocess.run([G, 'focus'])
    t0 = time.time(); k = 0
    t_first = None                               # 第一次真正划下去的时间（乱舞倒计时从这里开始）
    # 不限时：一直扫到退出乱舞。保险上限从「第一次划」开始算 10 秒（之前从发现乱舞算 15 秒，
    # 前面找起点耽误了 13 秒，结果刚扫完三种颜色就被保险上限切断了）
    while (t_first is None and time.time() - t0 < 20) or (t_first is not None and time.time() - t_first < 10):
        k += 1
        if k > 1:
            img = shot()
            if not is_rush(img):
                break
            b = board.detect(img)
        # 用户：每一笔都扫「除保留色外当前数量最多的颜色」，不按固定顺序
        counts = {}
        for p in b:
            if p[2] != keep:
                counts[p[2]] = counts.get(p[2], 0) + 1
        if not counts:
            time.sleep(0.1)
            continue
        # 按数量从多到少试；先严格（核对颜色），再放宽；都不行就从最下面一个非保留色开始（保证乱舞能推进）
        start = None
        for strict in (True, False):
            for c in sorted(counts, key=counts.get, reverse=True):
                start = stable_start(b, c, keep, img, strict)
                if start:
                    break
            if start:
                break
        if not start:
            others = [p for p in b if p[2] != keep]
            p0 = max(others, key=lambda p: p[1])
            start, c = (p0[0], p0[1]), p0[2]
        x, y = start
        t_first = t_first or time.time()
        zigzag_sweep(x, y + 20)                      # 扫完直接截下一张（截图本身要 ~0.4 秒，泡泡已经落得差不多）
        print(f'{time.time():.1f}', n, f'rush sweep {c} from ({x},{y})', flush=True)
    print(f'{time.time():.1f}', n, f'rush done: {k} sweeps in {time.time() - t0:.1f}s', flush=True)
    cv2.imwrite(str(LOG / f'rush_{n:03d}_end.png'), shot())


def selected_flags(before, during, pts):
    """连线中判断每个泡泡是否已选中：颜色明显变淡（饱和度降 >22）或中间出现白色菱形标记，任一满足就算"""
    a = cv2.cvtColor(before, cv2.COLOR_BGR2HSV).astype(np.int16)
    d = cv2.cvtColor(during, cv2.COLOR_BGR2HSV).astype(np.int16)
    out = []
    for x, y in pts:
        ys, xs = slice(y + 8, y + 42), slice(x - 22, x + 22)
        drop = max((a[ys, xs, 1] - d[ys, xs, 1]).mean(), (d[ys, xs, 2] - a[ys, xs, 2]).mean())   # 变淡 / 黑色变亮
        cy, cx = slice(y + 12, y + 36), slice(x - 12, x + 12)
        wa = ((a[cy, cx, 1] < 60) & (a[cy, cx, 2] > 235)).mean()
        wd = ((d[cy, cx, 1] < 60) & (d[cy, cx, 2] > 235)).mean()
        out.append(drop > 22 or wd - wa > 0.08)
    return out


LAST_DURING = None                               # 最近一次松手前核对的截图


def _broken_at(img, pts):
    """松手前判定（用户）：计划的个数 和 游戏显示的连接数 对不对得上。
    返回 k（只连上前 k 个）或 None（对上了 / 判断不了）。每次都写日志。"""
    global LAST_DURING
    during = shot()
    LAST_DURING = during
    n = len(pts)
    c = count.read_count(during)
    flags = selected_flags(img, during, pts)
    k0 = next((i for i, f in enumerate(flags) if not f), n)
    by_color = k0 if (0 < k0 < n and not any(flags[k0:])) else None
    if c is not None and c == n:
        verdict = None
    elif c is not None and c < n and not (n >= 10 and str(n).endswith(str(c))):
        verdict = c                       # 计数明确比计划少 → 信计数
    elif by_color:
        verdict = by_color                # 计数读不出 / 两位数可能只读到个位 → 看颜色
    else:
        verdict = None
    if verdict:                                   # 断链现场存图，方便看断在哪一步
        vis = during.copy()
        cv2.polylines(vis, [np.array([(x, y + 20) for x, y in pts])], False, (255, 0, 255), 4)
        cv2.imwrite(str(LOG / f'broken_{int(time.time() * 10)}_{verdict}of{n}.png'), vis)
    print(f'{time.time():.1f}', f'verify: plan {n}, game count {c if c is not None else "?"}, color {by_color or "ok"}'
          f' -> {"OK" if verdict is None else f"broken at {verdict}"}', flush=True)
    return verdict if verdict and 0 < verdict < n else None


def region_neighbors(region, seed):
    """游戏说发白区域里的同色泡泡互相连通（实测相邻眼睛距离可到 ~150px），
    所以从 120px 开始逐步放宽，取「刚好能把整片连起来」的最小距离（最多 180px）"""
    old = solver.LINK
    for L in range(120, 185, 6):
        solver.LINK = L; nb = solver.neighbors(region)
        seen, st = set(seed), list(seed)
        while st:
            q = st.pop()
            for j in nb[q]:
                if j not in seen:
                    seen.add(j); st.append(j)
        if len(seen) == len(region):
            break
    solver.LINK = old
    return nb, L


def extend_from(region, prefix, nb, budget=20000):
    """固定前缀（已选中的泡泡下标）往后接最长的路径；优先经过火焰泡泡"""
    best = prefix[:]; steps = 0
    key = lambda p: (sum(1 for i in p if region[i][4]), len(p))
    def dfs(path, seen):
        nonlocal best, steps
        steps += 1
        if key(path) > key(best):
            best = path[:]
        if steps > budget:
            return
        for j in sorted(nb[path[-1]], key=lambda q: (not region[q][4], len(nb[q]))):
            if j not in seen:
                seen.add(j); path.append(j); dfs(path, seen); path.pop(); seen.discard(j)
    dfs(prefix[:], set(prefix))
    return best


def diamonds(before, during, pts):
    """每个泡泡中间有没有选中时的白色菱形 ✦（比按下前多出明显的白色块）"""
    a = cv2.cvtColor(before, cv2.COLOR_BGR2HSV).astype(np.int16)
    d = cv2.cvtColor(during, cv2.COLOR_BGR2HSV).astype(np.int16)
    out = []
    for x, y in pts:
        cy, cx = slice(y + 12, y + 36), slice(x - 12, x + 12)
        wa = ((a[cy, cx, 1] < 60) & (a[cy, cx, 2] > 235)).mean()
        wd = ((d[cy, cx, 1] < 60) & (d[cy, cx, 2] > 235)).mean()
        out.append(wd - wa > 0.08)
    return out


def cancel_to_start(t, img, pts, k):
    """拖回起点取消（只剩起点 1 个时松手不算出手）。用户：BlueStacks 上往回拖经常没取消掉，
    直接松手就把已选的几个真的消掉了（长链变成两条短链）。所以松手前先截图确认只剩 1 个：
    计数没了（或 ≤1）且 pts[1:k] 都不再是选中状态。确认了才松手返回 True；两次都没确认就不松手，返回 False。"""
    for attempt in range(2):
        for x, y in reversed(pts[:k - 1]):
            t.slow(x, y + 20)
            if attempt:
                time.sleep(0.1)
        time.sleep(0.3)
        d = shot()
        # 只剩 1 个时：左上没有计数标签，pts[1:k] 中间也没有选中的白色菱形 ✦
        # （发白不算：能连的同色泡泡在只选 1 个时也可能还是淡色）
        label = count.find_label(d)
        dia = [p for p, f in zip(pts[1:k], diamonds(img, d, pts[1:k])) if f]
        if label is None and not dia:
            t.up(); time.sleep(0.4)
            return True
        cv2.imwrite(str(LOG / f'cancel_{int(time.time() * 10)}.png'), d)
        print(f'{time.time():.1f}', f'cancel to start not confirmed (label {label is not None}, diamonds {len(dia)}), attempt {attempt + 1}', flush=True)
        for x, y in pts[1:k]:                     # 第二次前先沿原路走回去，再重新往回拖
            t.slow(x, y + 20)
    return False


def replan_by_white(t, img, b, pts, k):
    """连线断在第 k 个（已选 pts[:k]），手指不松开，重新规划。原则（用户）：最大化连接长度，
    新路径绝不比原计划短。候选：
      - 原计划：从断点慢慢接着连（可能只是拖太快漏掉了）
      - 接着已选前缀走、避开断掉那一步的最长路径（可以往回退几个换条路）
      - 换起点的最长路径（原起点在链中间时；退回起点只剩 1 个松手，不算出手）
    区域 = 原计划的泡泡 + 现在发白的同色泡泡。按「成功率 × 长度」挑（见下面 P）。
    返回 (触摸, 新路径)。"""
    x, y = pts[k - 1]
    t.slow(x, y + 20)
    time.sleep(0.3)
    during = shot()
    c = next((p[2] for p in b if math.dist(p[:2], pts[0]) < 30), None)
    flame_at = lambda q: any(p[4] for p in b if math.dist(p[:2], q) < 30)
    region = [(x, y, c, 0.0, flame_at((x, y))) for x, y in pts]
    white = whiten.whitened_same_color(img, during, b, c, skip=pts) if c else []
    region += [p for p in white if all(math.dist(p[:2], q) > 30 for q in pts)]
    n = len(pts)
    nb, L = region_neighbors(region, range(k))
    for i in range(n - 1):                      # 原计划的每一步都算相邻（距离可能超过 L）
        if i + 1 not in nb[i]:
            nb[i].append(i + 1); nb[i + 1].append(i)
    if k < n:                                   # 断掉的那一步
        nb[k - 1] = [j for j in nb[k - 1] if j != k]; nb[k] = [j for j in nb[k] if j != k - 1]
    cands = [(n, False, True, k, 'retry', list(range(n)))]     # (长度, 不走断点, 不松手, 已选保留数, 名字, 路径)
    for j in range(k, 1, -1):
        p2 = extend_from(region, list(range(j)), nb)
        cands.append((len(p2), True, True, j, 'hold', p2))
    for s0 in range(len(region)):
        p2 = solver.longest_from(region, s0, nb)
        cands.append((len(p2), True, False, 0, 'restart', p2))
    # 用户：断了要重找起点。按实测成功率挑（farm.log 统计：原路重试 12/126、保留前段换路 21/94、换起点 38/81），
    # 期望连上的个数 = 成功率×新长度 +（失败时）保留下来的个数（实测三种失败时都约等于 k）；一样时取更长的
    P = {'retry': 0.10, 'hold': 0.22, 'restart': 0.47}
    ev = lambda c: P[c[4]] * c[0] + (1 - P[c[4]]) * k
    ln, _, _, j, how, best = max(cands, key=lambda c: (round(ev(c), 2), c[0]))
    print(f'{time.time():.1f}', f'replan by white: connected {k}/{n}, white {len(white)}, '
          f'pick {how} {ln} (link {L})', flush=True)
    if how == 'restart' and not cancel_to_start(t, img, pts, k):
        # 取消不掉就不能换起点（松手会把已选的消掉）：改用不松手的方案里最好的
        ln, _, _, j, how, best = max((c for c in cands if c[4] != 'restart'), key=lambda c: (round(ev(c), 2), c[0]))
        print(f'{time.time():.1f}', f'  -> keep holding, pick {how} {ln}', flush=True)   # 手指已经回到 pts[k-1]
    if how == 'restart':
        t = touch.Touch()
        t.down(region[best[0]][0], region[best[0]][1] + 20)
        rest = best[1:]
    else:
        j = next((i for i, q in enumerate(best) if q != i), len(best))   # 前 j 个和已选的一样
        j = min(j, k)
        for x, y in reversed(pts[j - 1:k]):     # 退回到分叉点（经过的已选泡泡依次取消）
            t.slow(x, y + 20)
        rest = best[j:]
    for q in rest:
        t.slow(region[q][0], region[q][1] + 20)
    return t, [region[q][:2] for q in best]


def extend_whitened(t, img, b, pts, reach=185, limit=8):
    """用户：游戏里已经发白的泡泡（= 能连上的）脚本也要连上。连完计划后先不松手：
    看核对时那张截图，链尾附近还有没连上的发白同色泡泡，就一个一个接上去（最近的优先），
    每接一个读一次计数确认；接不上就退回链尾，换下一个。"""
    c = next((p[2] for p in b if math.dist(p[:2], pts[0]) < 30), None)
    if not c:
        return pts
    tried = set()
    for _ in range(limit):
        white = [p[:2] for p in whiten.whitened_same_color(img, LAST_DURING, b, c, skip=pts)]
        cand = [q for q in white if q not in tried and math.dist(q, pts[-1]) <= reach]
        if not cand:
            break
        q = min(cand, key=lambda q: math.dist(q, pts[-1]))
        tried.add(q)
        t.slow(q[0], q[1] + 20)
        time.sleep(0.15)
        if _broken_at(img, pts + [q]) is None:
            pts = pts + [q]
            print(f'{time.time():.1f}', f'extend by white: +1 -> {len(pts)}', flush=True)
        else:
            t.slow(pts[-1][0], pts[-1][1] + 20)       # 没接上：回到链尾
    return pts


def finish_verified(t, img, pts, b=None):
    """用户：松手前确认计划的泡泡都连上了，没连全不松手。
    计数比计划少时先等一下再读（BlueStacks 输入有延迟，游戏可能还没处理完最后几步）；
    确实断了：已连上 ≥2 个按 replan_by_white 重新规划（不会比原计划短）；只连上 1 个就退回起点慢慢重连。
    只补一次，还不全就照现状松手。"""
    time.sleep(0.12)
    k = _broken_at(img, pts)
    if k:
        time.sleep(0.3)
        k = _broken_at(img, pts)
    if k:
        if b is not None and k >= 2:
            t, pts = replan_by_white(t, img, b, pts, k)
        else:
            print(f'{time.time():.1f}', f'chain only {k}/{len(pts)}, back to start (holding) and redo', flush=True)
            for x, y in reversed(pts[:k]):
                t.slow(x, y + 20)
            time.sleep(0.2)
            for x, y in pts[1:]:
                t.slow(x, y + 20)
        time.sleep(0.3)
        k = _broken_at(img, pts)
        if k:
            print(f'{time.time():.1f}', f'redo still {k}/{len(pts)}, releasing as is', flush=True)
    if not k and b is not None:
        pts = extend_whitened(t, img, b, pts)
    t.up()
    return pts


def chain_with_rescan(img, b, ch):
    """用户：脚本算的范围不一定等于游戏的可连通范围。
    连上前 2 个后游戏会把整片可连通的同色泡泡变白 → 以「已选 2 个 + 发白的」为准重新算最长链：
      - 新链从原起点出发：不松手，接着拖新链
      - 新链从别的泡泡出发：原路拖回起点取消（普通时间只剩 1 个松手不算出手），再按新链重连"""
    import math
    path = [b[i] for i in ch]
    if len(path) < 2:
        return 0
    c = path[0][2]
    t = touch.Touch()
    t.down(path[0][0], path[0][1] + 20)
    t.move(path[1][0], path[1][1] + 20)
    time.sleep(0.3)
    during = shot()
    t.slow(path[1][0], path[1][1] + 20)             # 截图停了一会儿：原地再报一次位置，游戏重新跟上手指
    white = [(p[0], p[1]) for p in whiten.whitened_same_color(img, during, b, c, skip=path[:2])]
    if bombs.detect(img, b):                       # 有炸弹时存原图，方便以后校准炸弹旁的发白识别
        k = int(time.time() * 10)
        cv2.imwrite(str(LOG / f'wb_before_{k}.png'), img); cv2.imwrite(str(LOG / f'wb_during_{k}.png'), during)
    # 炸弹旁边被挡住、没认出来的发白泡泡（用户：靠近炸弹的发白识别不好）
    extra = whiten.whitened_near_bombs(img, during, c, bombs.detect(img, b),
                                       known=[p[:2] for p in b if p[2] == c] + [p[:2] for p in path[:2]])

    def finish(pts, why):
        for x, y, *_ in pts:
            t.move(x, y + 20)
        finish_verified(t, img, [(p[0], p[1]) for p in path], b)
        print(f'{time.time():.1f}', f'chain {len(path)} ({why})', flush=True)
        return len(path)

    if not white:
        return finish(path[2:], 'no white')
    region = [path[0], path[1]] + [p for p in b if (p[0], p[1]) in white] + [(x, y, c, 0.0, False) for x, y in extra]
    white = white + extra
    cv2.imwrite(str(LOG / f'white_{int(time.time()*10)}.png'), board.draw(during, region))
    nb, L = region_neighbors(region, (0, 1))
    best = []
    for s0 in range(len(region)):
        cand = solver.longest_from(region, s0, nb, budget=20000)
        if (sum(region[i][4] for i in cand), len(cand)) > (sum(region[i][4] for i in best), len(best)):
            best = cand
    if len(best) <= len(path):
        return finish(path[2:], f'white {len(white)}, keep plan (region path {len(best)}, link {L})')
    new = [region[i] for i in best]
    if best[0] == 0 and len(best) > 1 and best[1] == 1:
        for x, y, *_ in new[2:]:
            t.move(x, y + 20)
        finish_verified(t, img, [(p[0], p[1]) for p in new], b); how = 'continue'
    else:
        if not cancel_to_start(t, img, [(p[0], p[1]) for p in path], 2):   # 拖回起点 → 只剩 1 个才松手
            for x, y, *_ in path[2:]:                # 取消不掉：不换起点，按原计划连完
                t.move(x, y + 20)
            finish_verified(t, img, [(p[0], p[1]) for p in path], b)
            print(f'{time.time():.1f}', f'chain {len(path)} (cancel failed, keep plan)', flush=True)
            return len(path)
        t = touch.Touch()
        t.down(new[0][0], new[0][1] + 20)
        for x, y, *_ in new[1:]:
            t.move(x, y + 20)
        finish_verified(t, img, [(p[0], p[1]) for p in new], b); how = 'restart'
    print(f'{time.time():.1f}', f'chain {len(path)} -> {len(new)} by white region ({how}, white {len(white)})', flush=True)
    return len(new)


def is_result(img):
    """结算页：底部橙色「次へ」按钮 + 上方大块米色卡片"""
    btn = cv2.cvtColor(img[1290:1345, 260:450], cv2.COLOR_BGR2HSV)
    orange = ((btn[..., 0] >= 10) & (btn[..., 0] <= 30) & (btn[..., 1] > 120) & (btn[..., 2] > 200)).mean()
    card = cv2.cvtColor(img[450:800, 100:600], cv2.COLOR_BGR2HSV)
    beige = ((card[..., 0] >= 15) & (card[..., 0] <= 35) & (card[..., 1] < 70) & (card[..., 2] > 200)).mean()
    return orange > 0.5 and beige > 0.4


def _two_buttons(img):
    """底部左白、右橙两个按钮（续关弹窗、撤退确认弹窗都是这个布局）"""
    l = cv2.cvtColor(img[1310:1365, 120:300], cv2.COLOR_BGR2HSV)
    r = cv2.cvtColor(img[1310:1365, 410:590], cv2.COLOR_BGR2HSV)
    white = ((l[..., 1] < 40) & (l[..., 2] > 225)).mean()
    orange = ((r[..., 0] >= 10) & (r[..., 0] <= 30) & (r[..., 1] > 120) & (r[..., 2] > 200)).mean()
    return white > 0.5 and orange > 0.5


def _beige_at(img, y):
    r = cv2.cvtColor(img[y - 20:y + 20, 150:560], cv2.COLOR_BGR2HSV)
    return ((r[..., 0] >= 10) & (r[..., 0] <= 35) & (r[..., 1] < 70) & (r[..., 2] > 190)).mean()


def is_continue_dialog(img):
    """输了：「コンティニュー確認」（右边是花宝玉续关，绝对不能点）。卡片较短，y=1100 处是模糊背景"""
    return _two_buttons(img) and _beige_at(img, 1100) < 0.3


def is_retreat_dialog(img):
    """「撤退確認」：卡片一直延伸到 y≈1240，y=1100 处是米色"""
    return _two_buttons(img) and _beige_at(img, 1100) > 0.7


def give_up():
    """死亡后不续关（用户定）：やめる → 撤退する → 次へ。按文字认弹窗，「コンティニュー」绝对不点。"""
    import nav
    for _ in range(10):
        img = shot(); t = nav.ocr(img)
        if nav.find(t, 'コンティニュー確認') or nav.find(t, 'コンティニューしますか'):
            tap(*(nav.find(t, 'やめる') or (210, 1338)))            # 左边「やめる」
        elif nav.find(t, '撤退確認') or nav.find(t, '撤退してよろしい'):
            tap(*(nav.find(t, '撤退する') or (495, 1340)))
        elif nav.find(t, '次へ'):
            tap(*nav.find(t, '次へ')); time.sleep(3)
            return
        elif nav.find(t, '戦う') or nav.find(t, '章変更'):
            return
        time.sleep(2.5)

RING = 90                                       # 相邻泡泡圆心间距约 90px
BOMB_REACH = {1: 1 * RING, 2: 2 * RING, 3: 3 * RING, 4: 0}   # 用户：1 级炸周围 1 圈邻居，2 级 2 圈（3 级按 3 圈估）


def bomb_for_flames(b, bb):
    """找能炸到最多火焰泡泡的炸弹，返回 (炸弹, 能炸到的火焰数)"""
    import math
    nb = solver.neighbors(b)
    best, best_s = None, 0
    for x, y, lv, r in bb:
        if lv >= 4:
            continue
        reach = r + BOMB_REACH[lv]
        s = 0
        for i, (fx, fy, c, _, f) in enumerate(b):
            if f and math.dist((x, y), (fx, fy + 15)) <= reach:
                s += 1
        if s > best_s:
            best, best_s = (x, y, lv), s
    return best, best_s


def densest_column(bubbles, half=55):
    xs = range(120, 600, 20)
    return max(xs, key=lambda c: sum(1 for x, *_ in bubbles if abs(x - c) <= half))


def run(max_moves=120, prefer=(), max_minutes=20):
    LOG.mkdir(exist_ok=True)
    idle = 0
    n = 0
    dud = []          # 点过但没反应的「炸弹」位置
    flame_age = 0     # 火焰已经存在了几次行动
    ougi_fail = {}    # 点了没反应的奥义次数（连续 3 次就先不点了，免得卡住）
    t_end = time.time() + max_minutes * 60
    while n < max_moves and time.time() < t_end:
        check_stop()
        quick = shot()
        if is_rush(quick):                 # 乱舞倒计时可能已经在走，不能先等落定
            keep = prefer[0] if prefer else None
            print(f'{time.time():.1f}', n, 'rush (quick), keep', keep, flush=True)
            rush_phase(keep, n, quick)
            continue
        img = wait_stable()
        cv2.imwrite(str(LOG / f'{int(time.time()*10)}.jpg'), cv2.resize(img, (354, 781)), [cv2.IMWRITE_JPEG_QUALITY, 80])
        if is_aim_screen(img):
            b = board.detect(img)
            x = densest_column(b)
            print(f'{time.time():.1f}', n, 'aim swipe at x', x, flush=True)
            drag([(x, 560), (x, 760), (x, 1000)])
            time.sleep(4)
            continue
        if is_rush(img):
            keep = prefer[0] if prefer else None
            print(f'{time.time():.1f}', n, 'rush, keep', keep, flush=True)
            rush_phase(keep, n, img)
            continue
        # 死亡弹窗 / 结算页先判断：输了时背景泛红，会被误认成奥义光圈，一直点奥义卡住
        if is_continue_dialog(img) or is_retreat_dialog(img):
            print(f'{time.time():.1f}', n, 'dead -> give up', flush=True)
            cv2.imwrite(str(LOG / 'dead.png'), img)
            give_up()
            return False
        if is_result(img):
            print(f'{time.time():.1f}', n, 'result', flush=True)
            cv2.imwrite(str(LOG / 'result.png'), img)
            # 戦闘結果 → 次へ → 獲得報酬 → 次へ；每次先确认还在结算页，避免误点地图上的「決定」
            RESULT_IMGS.append(img)
            for _ in range(4):
                cur = shot()
                if not is_result(cur):
                    break
                RESULT_IMGS.append(cur)
                tap(355, 1318); time.sleep(3)
            return True
        ready = [i for i, c in enumerate(CHARS) if pink_ratio(img, *c) > 0.09 and ougi_fail.get(i, 0) < 3]
        if ready:
            # 血量低时屏幕四周会泛红粉色，容易误判成奥义光圈 → 再看樱花：还写着「あと N」就是没攒满
            import nav
            crop = cv2.resize(img[1150:1360], None, fx=2, fy=2)          # 放大两倍才读得出樱花上的字
            ato = [x // 2 for x, y, w in nav.ocr(crop)
                   if w.startswith('あ') or (w.strip().isdigit() and len(w.strip()) <= 2)]
            def has_ato(i):                          # 樱花在角色左下方约 60px
                return any(abs(x - (CHARS[i][0] - 60)) < 90 for x in ato)
            ready = [i for i in ready if not has_ato(i)]
        ready_now = set(ready)
        if ready and TEAM and len(TEAM) == 3:
            # 用户定的优先级：≥7 的长链 > 三日月R > 消除（范围大→小）> 转色 > 生成炸弹（多→少）> 其他辅助
            ready.sort(key=lambda i: TEAM[i].get('rank', 9))
            b0 = board.detect(img)
            if len(b0) >= 30 and not any(p[4] for p in b0):
                ch0 = solver.best_chain(b0, prefer)
                if len(ch0) >= 7:
                    ready = []              # 先连长链，奥义留到下一步
        if ready:
            i = ready[0]
            gx, gy = glow_center(img, *CHARS[i])
            print(f'{time.time():.1f}', n, 'ougi', i, f'tap ({gx},{gy})', flush=True)
            tap(gx, gy - 40)                       # 点光圈中心偏上（角色身体）
            time.sleep(2.5)
            after = shot()
            if pink_ratio(after, *CHARS[i]) > 0.09 and not is_aim_screen(after):
                tap(gx, gy - 100)                  # 没反应：再点角色头部
                time.sleep(2.5)
                after = shot()
                if pink_ratio(after, *CHARS[i]) > 0.09 and not is_aim_screen(after):
                    ougi_fail[i] = ougi_fail.get(i, 0) + 1
                    print(f'{time.time():.1f}', n, f'ougi {i} tap failed x{ougi_fail[i]}', flush=True)
            continue
        b = board.detect(img)
        if len(b) < 12:
            idle += 1
            print(f'{time.time():.1f}', n, 'no board', len(b), flush=True)
            import nav
            tt = nav.ocr(img)
            if nav.find(tt, 'コンティニュー') or nav.find(tt, '撤退確認'):   # 颜色没认出的死亡弹窗
                print(f'{time.time():.1f}', n, 'dead (by text) -> give up', flush=True)
                give_up()
                return False
            if idle >= 6:
                break
            time.sleep(2)
            continue
        idle = 0
        bb_all = bombs.detect(img, b)
        if len(b) + 2 * len(bb_all) < 30:
            # 敌人奥义特写、动画中途等：棋盘不完整，先别出手（炸弹多时泡泡少是正常的）
            time.sleep(0.5)
            continue
        if len(b) < 30 and not any(p[4] for p in b):
            # 用户：泡泡少于 30 个（炸弹占了地方）才点炸弹腾出格子，先点等级最高的；平时炸弹留着合成
            cand = [k for k in bb_all if k[2] < 4 and all(math.dist(k[:2], d) > 60 for d in dud)]
            pick = max(cand, key=lambda k: k[2]) if cand else None
            if pick:
                print(f'{time.time():.1f}', n, f'bomb lv{pick[2]} (only {len(b)} bubbles, make room)', flush=True)
                tap(pick[0], pick[1]); time.sleep(2.2)
                if same_layout(b, board.detect(shot())):
                    dud.append(pick[:2])
                continue
        # 用户：优先消队伍角色奥义需要的颜色（奥义已经亮了的角色不用再攒）
        need = tuple(c for i, c in enumerate(sakura_colors(img)) if c and i not in ready_now)
        # 用户（2026-10-22）：最大化长链；奥义需要的颜色只稍微优先（solver.best_chain_team）
        solver.OBST = obstacles.detect(img)
        if any(solver.OBST.values()):
            print(f'{time.time():.1f}', n, 'obstacles', {k: v for k, v in solver.OBST.items() if v}, flush=True)
        ch = solver.best_chain_team(b, set(need))
        n_flame = sum(1 for p in b if p[4])
        if not n_flame:
            flame_age = 0
        if n_flame:
            # 火焰泡泡出现后只有 2 次行动（连线算行动，炸弹/奥义不算）。用户定：
            #   第 1 回合：先找链（能整块清掉某片火焰 / 清掉一半以上），不行再用炸弹
            #   第 2 回合：必须先用炸弹（奥义亮了的上面已经先放了），能炸到火焰的炸弹全部用掉，再连线
            import math
            whole = solver.chain_clearing_cluster(b)
            if whole:
                ch = whole
            in_chain = sum(1 for i in ch if b[i][4])
            urgent = flame_age >= 1
            if urgent or (not whole and in_chain * 2 < n_flame):
                cand = [k for k in bombs.detect(img, b) if all(math.dist(k[:2], d) > 60 for d in dud)]
                bomb, sc = bomb_for_flames(b, cand)
                if bomb and (urgent or sc > in_chain):
                    print(f'{time.time():.1f}', n, f'bomb lv{bomb[2]} hits {sc} flames (turn {flame_age + 1}, chain {in_chain}/{n_flame})', flush=True)
                    tap(bomb[0], bomb[1]); time.sleep(2.5)
                    if same_layout(b, board.detect(shot())):
                        dud.append(bomb[:2])
                        print(f'{time.time():.1f}', n, f'not a bomb at {bomb[:2]}, skip', flush=True)
                    continue
        ch = orient_for_merge(b, ch, bombs.detect(img, b))
        path = [b[i] for i in ch]
        print(f'{time.time():.1f}', n, 'chain', len(path), path[0][2] if path else None, flush=True)
        if len(path) >= 2:
            chain_with_rescan(img, b, ch)
            n += 1
            if n_flame:
                flame_age += 1
        time.sleep(0.4)   # 等消除动画开始，泡泡落定交给 wait_stable


if __name__ == '__main__':
    board.THRESH = 0.5
    run(prefer=tuple(sys.argv[1:]))
