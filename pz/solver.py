"""找最长的同色连线。泡泡之间眼睛距离 <= LINK 就算相邻。"""
import math

LINK = 112
# 当前盘面的障碍物（play 每回合设置）：{'shell': [(x, y)], 'box': [(x, y)]}
OBST = {}
SHELL_BONUS, BOX_PENALTY = 3, 2


def obst_score(bubbles, ch):
    """用户：贝壳旁边消除 → 变随机道具（加分）；箱子旁边消除 → 变出 5 个黑色泡泡（扣分）"""
    import obstacles
    near = lambda pts: sum(1 for p in pts if any(obstacles.touching(bubbles[i], [p]) for i in ch))
    return SHELL_BONUS * near(OBST.get('shell', [])) - BOX_PENALTY * near(OBST.get('box', []))


def neighbors(bubbles):
    nb = {i: [] for i in range(len(bubbles))}
    for i, a in enumerate(bubbles):
        for j, b in enumerate(bubbles):
            if i < j and a[2] == b[2] and math.dist(a[:2], b[:2]) <= LINK:
                nb[i].append(j); nb[j].append(i)
    return nb


def longest_chain(bubbles, budget=200000, color=None):
    """DFS 找最长简单路径；返回泡泡下标列表。color 指定只找某种颜色"""
    nb = neighbors(bubbles)
    best = []
    steps = 0
    def dfs(path, seen):
        nonlocal best, steps
        steps += 1
        if len(path) > len(best):
            best = path[:]
        if steps > budget:
            return
        # 先走邻居少的（Warnsdorff 启发），容易走得更长
        for j in sorted(nb[path[-1]], key=lambda k: len(nb[k])):
            if j not in seen:
                seen.add(j); path.append(j)
                dfs(path, seen)
                path.pop(); seen.discard(j)
    for i in sorted(range(len(bubbles)), key=lambda k: len(nb[k])):
        if color is None or bubbles[i][2] == color:
            steps = 0
            dfs([i], {i})
    return best


def longest_from(bubbles, start, nb, budget=20000):
    """从 start 出发的最长同色路径（优先经过火焰泡泡）"""
    best = [start]; steps = 0
    def dfs(path, seen):
        nonlocal best, steps
        steps += 1
        key = lambda p: (sum(1 for i in p if bubbles[i][4]), len(p))
        if key(path) > key(best):
            best = path[:]
        if steps > budget:
            return
        for j in sorted(nb[path[-1]], key=lambda k: (not bubbles[k][4], len(nb[k]))):
            if j not in seen:
                seen.add(j); path.append(j); dfs(path, seen); path.pop(); seen.discard(j)
    dfs([start], {start})
    return best


def best_chain(bubbles, prefer=(), prefer_mult=1.3, flame_bonus=8):
    """候选 = 每种颜色的最长链 + 从每个火焰泡泡出发的最长链。
    评分 = 长度 × (偏好色 1.3) + 每个火焰泡泡 8 分。
    火焰泡泡放着两步后会打人，含火焰的短链也要能赢过普通长链。"""
    nb = neighbors(bubbles)
    cands = []
    for c in {b[2] for b in bubbles}:
        cands.append(longest_chain(bubbles, budget=40000, color=c))
    for i, b in enumerate(bubbles):
        if b[4]:
            cands.append(longest_from(bubbles, i, nb))
    best, best_s = [], float("-inf")    # 箱子扣分可能让分数为负，也要能选
    for ch in cands:
        if len(ch) < 2:
            continue
        c = bubbles[ch[0]][2]
        s = len(ch) * (prefer_mult if c in prefer else 1) + flame_bonus * sum(1 for i in ch if bubbles[i][4]) + obst_score(bubbles, ch)
        if s > best_s:
            best, best_s = ch, s
    return best


def flame_clusters(bubbles, link=None):
    """火焰泡泡按位置分块（相邻距离 ≤ LINK 就算同一块，不管颜色）"""
    link = link or LINK
    fl = [i for i, b in enumerate(bubbles) if b[4]]
    groups, seen = [], set()
    for i in fl:
        if i in seen:
            continue
        stack, g = [i], []
        seen.add(i)
        while stack:
            k = stack.pop(); g.append(k)
            for j in fl:
                if j not in seen and math.dist(bubbles[k][:2], bubbles[j][:2]) <= link:
                    seen.add(j); stack.append(j)
        groups.append(set(g))
    return groups


def chain_clearing_cluster(bubbles, budget=20000):
    """找能一次清掉某一整块火焰的链（块越大越好）。没有就返回 []"""
    nb = neighbors(bubbles)
    best, best_key = [], (0, 0)
    for g in flame_clusters(bubbles):
        if len({bubbles[i][2] for i in g}) != 1:
            continue                       # 一块里有不同颜色，一条链清不完
        for start in g:
            ch = longest_from(bubbles, start, nb, budget)
            if len(ch) >= 2 and g <= set(ch):
                key = (len(g), len(ch))
                if key > best_key:
                    best, best_key = ch, key
                break
    return best


def best_chain_team(bubbles, need, bomb_len=7):
    """用户定的普通时间顺序：
    - 队伍奥义需要的颜色（need）：正常选最长链（火焰泡泡加分）
    - 不需要的颜色：只有能连到 ≥7 个（生成炸弹）才考虑
    - 两边都没有合格的链时，退回到任意颜色的最长链（总得走一步）"""
    if not need:
        return best_chain(bubbles)
    need = set(need) | {'black'}           # 用户：箱子变出来的黑色泡泡也要消，不限 7 个
    best, best_s = [], float("-inf")    # 箱子扣分可能让分数为负，也要能选
    for c in {b[2] for b in bubbles}:
        ch = longest_chain(bubbles, budget=40000, color=c)
        if len(ch) < 2:
            continue
        if c not in need and len(ch) < bomb_len:
            continue
        s = len(ch) + 8 * sum(1 for i in ch if bubbles[i][4]) + obst_score(bubbles, ch)
        if s > best_s:
            best, best_s = ch, s
    return best or best_chain(bubbles)
