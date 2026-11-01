"""界面导航：OCR、心数、章节切换、选关、选队、读掉落。坐标都是 2x 截图像素。"""
import json, math, re, subprocess, time
from pathlib import Path
import cv2, numpy as np
import play

ROOT = Path(__file__).parent.parent
ITEMS = Path(__file__).parent / 'items'


def log(*a):
    line = f'{time.strftime("%H:%M:%S")} ' + ' '.join(str(x) for x in a)
    print(line, flush=True)        # farm.py 把 stdout 同时写进 farm.log


def ocr(img):
    """返回 [(cx, cy, text)]"""
    p = ROOT / 'refs' / '_ocr.png'
    cv2.imwrite(str(p), img)
    out = subprocess.run([str(ROOT / 'ocr'), str(p)], capture_output=True, text=True).stdout
    res = []
    for line in out.splitlines():
        parts = line.split(' ')
        if len(parts) < 5:
            continue
        x, y, w, h = map(int, parts[:4])
        res.append((x + w // 2, y + h // 2, ' '.join(parts[4:])))
    return res


def find(texts, s):
    return next(((x, y) for x, y, t in texts if s in t), None)


# ---------- 心 ----------
def hearts(img):
    """左上角心数：红心个数（最多 5）+ 超出部分显示的「+N」"""
    h = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    n = 0
    for x in (52, 88, 122, 156, 190):
        r = h[240:265, x - 12:x + 12]
        if (((r[..., 0] <= 8) | (r[..., 0] >= 170)) & (r[..., 1] > 120)).mean() > 0.3:
            n += 1
    if n >= 4:                                   # 满 5 颗时右边可能有「+N」
        for x, y, s in ocr(img[200:290, 0:330]):
            m = re.search(r'\+\s*(\d+)', s)
            if m:
                return 5 + int(m.group(1))
    return n


# ---------- 章节 ----------
def current_chapter(texts):
    for _, _, t in texts:
        m = re.search(r'第\s*(\d+)\s*章', t)
        if m:
            return int(m.group(1))
    return None


def change_chapter(ch):
    """地图上点「章変更」→ 在海图里找「第N章」点它；找不到就上下拖动海图再找"""
    play.tap(602, 318); time.sleep(2)
    for k in range(6):
        t = ocr(play.shot())
        for x, y, s in t:
            m = re.search(r'第\s*(\d+)\s*章', s)
            if m and int(m.group(1)) == ch:
                play.tap(x, y); time.sleep(3)
                return True
        # 海图：第 1 章在下，越往上越新
        if k < 3:
            play.drag([(355, 600), (355, 800), (355, 1000)])
        else:
            play.drag([(355, 1000), (355, 800), (355, 600)])
        time.sleep(1.2)
    play.tap(355, 1338); time.sleep(1.5)          # とじる
    return False


# ---------- 选队 ----------
DOTS = (289, 321, 354, 386, 419)


def team_index(img):
    """队伍选择页下方 5 个小圆点，绿色实心的是当前队（0 起）"""
    h = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    for i, x in enumerate(DOTS):
        p = h[1228:1238, x - 3:x + 3].reshape(-1, 3).mean(0)
        if 30 <= p[0] <= 45 and p[1] > 120:
            return i
    return None


def team_name(texts):
    """绿底条里的队名（y≈855，x 80~450）"""
    cands = [(x, s) for x, y, s in texts if 835 <= y <= 875 and 60 <= x <= 460]
    return min(cands)[1] if cands else ''


def select_team(target):
    """target: 队名（字符串）或第几队（1~5 的数字）。在队伍选择页用左右黄箭头切换。"""
    want_idx = int(target) - 1 if str(target).isdigit() else None
    for _ in range(6):
        img = play.shot(); t = ocr(img)
        idx, name = team_index(img), team_name(t)
        if want_idx is not None and idx == want_idx:
            return name
        if want_idx is None and target and target.lower() in name.lower():
            return name
        if want_idx is not None and idx is not None:
            right = (want_idx - idx) % 5 <= 2
        else:
            right = True
        play.tap(657 if right else 50, 1035); time.sleep(1.2)
    return None


# ---------- 走到目标关的队伍选择页 ----------
def slow_pan(dx, y=560):
    """地图横向平移 dx 像素：按下 → 慢慢拖 → 停 0.4 秒 → 松开（没有惯性，位置可控）"""
    import touch
    if abs(dx) < 20:
        return
    x0 = 355 - dx / 2
    t = touch.Touch()
    t.down(x0, y)
    steps = max(2, int(abs(dx) / 60))
    for i in range(1, steps + 1):
        t.move(x0 + dx * i / steps, y)
    time.sleep(0.4)
    t.up()


def day_changed(t):
    """换天弹窗（日付が変わりました。絵巻船に戻ります。）的「はい」按钮位置，没有就 None"""
    if find(t, '日付が変わ') or find(t, '絵巻船に戻'):
        return next(((x, y) for x, y, w in t if w.strip() == 'はい'), (355, 1335))
    return None


def goto_team_select(stage, team=None):
    ch, no = stage.split('-')
    ch = int(ch)
    for _ in range(25):
        img = play.shot(); t = ocr(img)
        if find(t, f'{ch}章{no}話'):
            if team:
                got = select_team(team)
                if got is None:
                    log('找不到队伍', team); return False
                log('队伍:', got)
            return True
        if find(t, 'コンティニュー確認') or find(t, '撤退確認'):   # 死亡后的弹窗 → 不续关，撤退
            play.give_up(); continue
        if find(t, '次へ'):
            play.tap(*find(t, '次へ')); time.sleep(3); continue
        if find(t, '戦う'):                       # 别的关的队伍页 → とじる
            play.tap(110, 1340); time.sleep(2); continue
        if find(t, '出陣'):
            play.tap(*find(t, '出陣')); time.sleep(3.5); continue
        if find(t, '章変更'):
            cur = current_chapter(t)
            if cur is not None and cur != ch:
                change_chapter(ch); continue
            node = find(t, stage)
            if node:
                play.tap(node[0], node[1] - 50); time.sleep(1.5)
                if find(ocr(play.shot()), '決定'):
                    play.tap(355, 1335); time.sleep(3)
                continue
            # 当前章节里没看到 → 按看得到的关卡标签算出目标关的位置（相邻关卡横向约 156px），
            # 慢慢拖过去、停住再松手（避免惯性滑过头）
            seen = [(x, int(m.group(1))) for x, y, w in t for m in [re.search(rf'{ch}\s*-\s*(\d+)', w)] if m]
            if seen:
                x0, n0 = seen[0]
                shift = 355 - (x0 + (int(no) - n0) * 156)
            else:
                shift = 450                                          # 一个都没看到：往前翻
            slow_pan(max(-520, min(520, shift)))
            time.sleep(1); continue
        if resume_dialog(t):                       # 上一局没打完 → 再開する，交给 farm 接着打
            do_resume(t); return 'resume'
        if server_error(t):
            log('服务器通信错误，点「はい」'); play.tap(*server_error(t)); time.sleep(4); continue
        if day_changed(t):                         # 换天：「日付が変わりました。絵巻船に戻ります。」→ はい
            log('换天了，点「はい」回绘卷船'); play.tap(*day_changed(t)); time.sleep(5); continue
        # 「通信エラーが発生しました。」（タイトルへ / リトライ）：先リトライ，3 次不行回标题页
        if find(t, '通信エラー') and find(t, 'リトライ'):
            play.shot(); time.sleep(1); continue     # 由 play.shot 统一处理（重试 3 次不行就回标题页）
        # 换天后：狐狸「昨日の日報の確認をお願いします！」没有按钮 → 点它抱着的卷轴，打开日报（日报本身用 とじる 关）
        if find(t, '日報の確認'):
            log('换天后的日报提示，点卷轴'); play.tap(355, 950); time.sleep(3); continue
        # 弹窗（升级、课题达成、通知等）：点「とじる / OK / 閉じる」关掉
        btn = next(((x, y) for x, y, w in t if w.strip() in ('とじる', 'OK', '閉じる', 'ＯＫ')), None)
        if btn:
            log('关闭弹窗：', ' / '.join(w for _, _, w in t[:4]))
            play.tap(*btn); time.sleep(2); continue
        # 其他页面：有「ホーム」按钮就点它回主页；主页上直接点出陣；都认不出（加载中）就等一下
        if find(t, 'ホーム'):
            play.tap(*find(t, 'ホーム')); time.sleep(3); continue
        if find(t, '召喚') or find(t, '戦支度') or find(t, 'よろず屋'):
            play.tap(350, 1235); time.sleep(3.5); continue
        if not _is_bs() and _find_home_icon(img):    # 在 iPhone 主屏幕（游戏没开）→ 打开游戏
            open_game(); continue
        if find(t, 'はじめる'):                    # 开始页面（标题 + はじめる 按钮）→ 点它进游戏
            log('开始页面，点「はじめる」')
            play.tap(*find(t, 'はじめる')); time.sleep(6); continue
        time.sleep(2)                              # 书架加载画面等认不出的页面：等一下
    cv2.imwrite(str(ROOT / 'refs' / f'nav_fail_{int(time.time())}.png'), img)
    log('导航失败，最后的画面存到了 refs/nav_fail_*.png，识别到的文字：', ' / '.join(w for _, _, w in t[:8]))
    return False


def resume_dialog(t):
    """重开游戏时上一局没打完：「中断データがあります / 挑戦中の戦闘を再開しますか？」（撤退する / 再開する）
    → 返回「再開する」的位置（票 / 心已经花了，接着打）"""
    if find(t, '中断データ') or find(t, '戦闘を再開'):
        return find(t, '再開する') or (494, 1339)


def do_resume(t):
    """点「再開する」。用户 2026-11-01：要点两次 —— 点完再看几次，弹窗还在（或又弹一次）就再点，最多 4 次"""
    for i in range(4):
        log(f'有没打完的战斗，点「再開する」接着打（第 {i + 1} 次）')
        play.tap(*resume_dialog(t)); time.sleep(3)
        t = ocr(play._shot())
        if not resume_dialog(t):
            time.sleep(3); return


def server_error(t):
    """「ゲームサーバーとの通信中にエラーが発生しました。（2-103）」只有「はい」→ 返回它的位置"""
    if find(t, '通信中にエラー') or find(t, 'エラーが発生'):
        return next(((x, y) for x, y, w in t if w.strip() == 'はい'), None)


# ---------- 活动（大討伐 BIG ト餓鬼）----------
EVENT_STAGES = ('大讨伐', '大討伐', 'event', '活动', 'イベント')   # App「关卡」填 大讨伐（旧写法 event 也认）


def tickets(img):
    """活动票数（活动页 / 挑战页左上角，不能补充）；读不出返回 None"""
    for x, y, s in ocr(img[200:290, 0:330]):
        m = re.match(r'\s*(\d+)', s)               # 有时和旁边的「+」读成一个词：「22＋」
        if m:
            return int(m.group(1))
    return None


def is_event_battle_page(t):
    """活动挑战页：首领 + 队伍 +「戦う」（消耗 1 张票）"""
    return find(t, '戦う') and (find(t, '有利刀種') or find(t, 'BIG') or find(t, 'ボーナス'))


def goto_event(team=None):
    """走到活动挑战页（有「戦う」的那页），可选切换队伍"""
    for _ in range(25):
        img = play.shot(); t = ocr(img)
        if is_event_battle_page(t):
            if team:
                got = select_team(team)
                if got is None:
                    log('找不到队伍', team); return False
                log('队伍:', got)
            return True
        if find(t, '挑戦') and find(t, '報酬リスト'):      # 活动首页 → 挑戦
            play.tap(*find(t, '挑戦')); time.sleep(3); continue
        if find(t, 'コンティニュー確認') or find(t, '撤退確認'):
            play.give_up(); continue
        if resume_dialog(t):                       # 上一局没打完 → 再開する，交给 farm 接着打
            do_resume(t); return 'resume'
        if server_error(t):
            log('服务器通信错误，点「はい」'); play.tap(*server_error(t)); time.sleep(4); continue
        if day_changed(t):
            log('换天了，点「はい」'); play.tap(*day_changed(t)); time.sleep(5); continue
        if find(t, '日報の確認'):
            play.tap(355, 950); time.sleep(3); continue
        if find(t, '次へ'):
            play.tap(*find(t, '次へ')); time.sleep(3); continue
        if find(t, '通信エラー') and find(t, 'リトライ'):
            play.shot(); time.sleep(1); continue
        # 主页点「イベント」弹出的活动列表（标题「イベント」在 y≈423）→ 用户：点第一个活动
        if any(w.strip() == 'イベント' and 400 <= y <= 445 for x, y, w in t) and find(t, 'とじる'):
            log('活动列表，点第一个活动'); play.tap(355, 545); time.sleep(3.5); continue
        btn = next(((x, y) for x, y, w in t if w.strip() in ('とじる', 'OK', '閉じる', 'ＯＫ')), None)
        if btn:
            log('关闭弹窗：', ' / '.join(w for _, _, w in t[:4]))
            play.tap(*btn); time.sleep(2); continue
        if find(t, '召喚') or find(t, '戦支度') or find(t, 'よろず屋'):   # 主页 → 左下「イベント」
            play.tap(80, 1225); time.sleep(3.5); continue
        if find(t, 'はじめる'):
            play.tap(*find(t, 'はじめる')); time.sleep(6); continue
        time.sleep(2)
    cv2.imwrite(str(ROOT / 'refs' / f'nav_fail_{int(time.time())}.png'), img)
    log('走不到活动挑战页，最后的画面存到了 refs/nav_fail_*.png，识别到的文字：', ' / '.join(w for _, _, w in t[:8]))
    return False


# ---------- 掉落 ----------
def _catalog():
    cat = json.load(open(ITEMS / 'catalog.json'))
    return [(name, cv2.imread(str(ITEMS / v['icon']))) for name, v in cat.items()]


_CAT = None


def read_rewards(img):
    """结算页「獲得報酬」区域：圆形物品图标 + 右下数量；小判数量在底部。返回 {名字: 数量}"""
    global _CAT
    _CAT = _CAT or _catalog()
    y0, y1, x0, x1 = 490, 770, 80, 640
    roi = img[y0:y1, x0:x1]
    hits = []
    for name, icon in _CAT:
        for scale in (0.95, 1.0):
            t = cv2.resize(icon, None, fx=scale, fy=scale)
            res = cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED)
            _, mv, _, ml = cv2.minMaxLoc(res)
            if mv > 0.72:
                hits.append((mv, name, ml[0] + x0 + t.shape[1] // 2, ml[1] + y0 + t.shape[0] // 2))
    hits.sort(reverse=True)
    kept = []
    for s, name, x, y in hits:
        if all(math.dist((x, y), (a, b)) > 60 for _, _, a, b in kept):
            kept.append((s, name, x, y))
    texts = ocr(img)
    out = {}
    for _, name, x, y in kept:
        nums = [(math.dist((x + 55, y + 35), (tx, ty)), s) for tx, ty, s in texts
                if s.strip().isdigit() and 0 < tx - x < 110 and -10 < ty - y < 90]
        out[name] = out.get(name, 0) + (int(min(nums)[1]) if nums else 1)
    coin = [s for tx, ty, s in texts if 780 <= ty <= 830 and tx > 450 and s.strip().isdigit()]
    if coin:
        out['小判'] = int(coin[0])
    return out


# ---------- 关游戏 ----------
def _find_game_card(img):
    """多任务界面里找ぱずぎり的卡片：先找文字标签，找不到就用游戏图标模板（卡片只露一半时只有图标）"""
    t = ocr(img)
    lab = next(((x, y) for x, y, s in t if 'ぱずぎり' in s or 'ぱずき' in s), None)
    if lab:
        return min(lab[0] + 120, 600), lab[1] + 420
    tpl = cv2.imread(str(Path(__file__).parent / 'tpl_game_icon.png'))
    res = cv2.matchTemplate(img[150:380], tpl, cv2.TM_CCOEFF_NORMED)
    _, v, _, (x, y) = cv2.minMaxLoc(res)
    if v > 0.75:
        return min(x + 23 + 60, 640), 800
    return None


def _is_bs():
    import os
    return os.environ.get('PAZ_DEVICE') == 'bluestacks'


def close_game():
    """打完后关游戏：iPhone 镜像 ⌘2 打开多任务界面 → 找到ぱずぎり的卡片往上划掉 → ⌘1 回主屏幕。
    只划认出是ぱずぎり的卡片，找不到就什么都不划。"""
    if _is_bs():
        log('BlueStacks 模式暂不支持自动关游戏，跳过'); return False
    key = str(ROOT / 'key')
    subprocess.run([str(ROOT / 'g.sh'), 'focus'])
    subprocess.run([key, '19', 'cmd']); time.sleep(1.5)        # ⌘2 多任务
    closed = False
    card = _find_game_card(play.shot())
    if card:
        cx, cy = card
        play.drag([(cx, cy), (cx, cy - 300), (cx, 150)])
        time.sleep(1.2)
        closed = _find_game_card(play.shot()) is None
    subprocess.run([str(ROOT / 'g.sh'), 'focus'])
    subprocess.run([key, '18', 'cmd']); time.sleep(1)           # ⌘1 回主屏幕
    log('已关闭游戏' if closed else '多任务里没找到ぱずぎり，没有关')
    return closed


# ---------- 打开游戏 ----------
def _find_home_icon(img):
    tpl = cv2.imread(str(Path(__file__).parent / 'tpl_home_icon.png'))
    res = cv2.matchTemplate(img[150:1450], tpl, cv2.TM_CCOEFF_NORMED)
    _, v, _, (x, y) = cv2.minMaxLoc(res)
    return (x + 50, y + 150 + 50) if v > 0.8 else None


def open_game():
    """iPhone 镜像 ⌘1 回主屏幕 → 找ぱずぎり图标点开（第 1 页找不到就左右翻页）"""
    if _is_bs():
        log('BlueStacks 模式：请先在 BlueStacks 里打开游戏'); return False
    key = str(ROOT / 'key')
    subprocess.run([str(ROOT / 'g.sh'), 'focus'])
    subprocess.run([key, '18', 'cmd']); time.sleep(1.5)
    subprocess.run([key, '18', 'cmd']); time.sleep(1.2)      # 已在主屏幕时再按一次 = 回到第 1 页
    for k in range(6):
        pos = _find_home_icon(play.shot())
        if pos:
            play.tap(*pos); time.sleep(8)
            log('已打开游戏')
            return True
        play.drag([(600, 700), (350, 700), (100, 700)])          # 翻到下一页
        time.sleep(1.2)
    log('主屏幕上没找到ぱずぎり图标')
    return False


# ---------- 用宝玉（花珠子）补充体力 ----------
def heart_rows(t):
    """「ハート回復」弹窗里的每一行：[(名字, 所持数, つかう按钮坐标, 宝玉费用)]。
    一行 = 左边名字 + 右上「所持：N」+ 右下「つかう」（refs/heart_popup.png：宝玉在 y≈730，つかう 在 y≈784）"""
    rows = []
    for x, y, s in t:
        if '所持' not in s:
            continue
        digits = ''.join(ch for ch in s.split('所持')[-1] if ch.isdigit())
        n = int(digits) if digits else 0
        btn = next(((bx, by) for bx, by, bs in t if 'つかう' in bs and 20 <= by - y <= 100 and abs(bx - x) < 120), None)
        name = next((ns for nx, ny, ns in t if nx < 330 and abs(ny - y) < 25 and '所持' not in ns), '')
        cost = next((int(cs) for cx, cy, cs in t if cs.strip().isdigit() and cx < 200 and 40 <= cy - y <= 110), None)
        rows.append((name, n, btn, cost))
    return rows


def buy_hearts(max_cost=50):
    """爱心右边的「+」→「ハート回復」弹窗。用户：先用补心道具（所持 >0 的非宝玉行），道具用完了才用宝玉 50 个回复 10 颗心。
    之后如果还有确认弹窗，只点肯定的按钮（つかう/はい/OK/回復），绝不点购买宝玉之类的按钮。
    成功返回 True（心数变多），否则 False。"""
    before = hearts(play.shot())
    play.tap(247, 252); time.sleep(2)
    t = ocr(play.shot())
    if not find(t, 'ハート回復'):
        log('没打开「ハート回復」弹窗'); return False
    rows = heart_rows(t)
    items = [r for r in rows if '宝玉' not in r[0] and r[1] > 0 and r[2]]
    jade = next((r for r in rows if '宝玉' in r[0] and r[2]), None)
    if items:
        name, n, btn, _ = items[0]
        log(f'用道具补充体力：{name}（所持 {n}）')
    elif jade:
        name, n, btn, cost = jade
        if cost is not None and cost > max_cost:
            log(f'补充体力要 {cost} 宝玉，超过上限 {max_cost}，不买'); play.tap(350, 1325); return False
        log(f'用宝玉补充体力（所持 {n}）')
    else:
        log(f'补心弹窗里没有能用的道具或宝玉：{rows}'); play.tap(350, 1325); return False
    play.tap(*btn); time.sleep(2)
    for _ in range(3):                                        # 可能的确认弹窗
        t = ocr(play.shot())
        if any(k in s for _, _, s in t for k in ('購入', 'ショップ', '足りません', '不足')):
            log('宝玉不足或跳到了商店，停止补充'); play.tap(350, 1325); return False
        btn = next(((x, y) for x, y, s in t if s.strip() in ('つかう', 'はい', 'OK', '回復する', '使う')), None)
        if not btn:
            break
        play.tap(*btn); time.sleep(2)
    for _ in range(2):                                        # 关掉剩下的弹窗
        t = ocr(play.shot())
        if find(t, 'とじる'):
            play.tap(*find(t, 'とじる')); time.sleep(1.5)
    after = hearts(play.shot())
    if after <= before:                                       # 心数动画慢：再等一下读一次
        time.sleep(2); after = hearts(play.shot())
    log(f'补充体力：{before} → {after} 颗心')
    return after > before
