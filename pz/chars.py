"""角色识别 + 奥义信息：队伍选择页的三张卡片 ↔ 角色技能.md 里的头像。"""
import re
from pathlib import Path
import cv2, numpy as np

ROOT = Path(__file__).parent.parent
CARD_X = (206, 356, 506)


def load_table():
    rows = []
    for line in open(ROOT / '角色技能.md', encoding='utf-8'):
        m = re.match(r'\| <img src="([^"]+)"[^|]*\| *([^|]*?) *\| *([^|]*?) *\| *(白|彩) *\| *([^|]*?) *\| *(赤|青|黄|緑) *\| *(\d+) *\| *([^|]*?) *\| *([^|]*?) *\| *([^|]*?) *\|', line)
        if m:
            img, name, pos, frame, ougi, col, need, typ, eff, how = m.groups()
            rows.append(dict(img=str(ROOT / img), name=name, frame=frame, ougi=ougi,
                             color={'赤': 'red', '青': 'blue', '黄': 'yellow', '緑': 'green'}[col],
                             need=int(need), type=typ, effect=eff, how=how))
    for r in rows:
        r['rank'], r['cat'] = rank(r)
    return rows


def rank(r):
    """用户定的普通关卡奥义优先级（数字越小越优先）：
    1 三日月宗近R（全屏）> 2 消除类（按范围：全屏>大>中>小>特小，随机按个数折算）> 3 转色 > 4 生成炸弹（3>2>1）> 5 其他辅助"""
    e, t, n = r['effect'], r['type'], r['name']
    if n == '三日月宗近R':
        return 1.0, '全屏'
    if '聚' in e or '聚怪' in t:
        return 5.0, '辅助'
    if '変幻' in r['ougi'] or '变色' in t or '转变' in e or '变成' in e:
        return 3.0, '转色'
    if '炸弹' in e and ('生成' in e) and '消除' not in e and '范围' not in e:
        k = int(re.search(r'(\d+) 个炸弹', e).group(1)) if re.search(r'(\d+) 个炸弹', e) else 1
        return 4.0 + (3 - k) * 0.1, f'炸弹{k}'
    sizes = [('全屏', 0.0), ('大', 0.1), ('中', 0.2), ('小', 0.3), ('特小', 0.4)]
    m = re.search(r'最多 *(\d+) *个', e) or re.search(r'(\d+) 个孤立', e)
    if m:                                   # 随机消除：10≈中 5≈小 3≈特小
        k = int(m.group(1))
        return 2.0 + (0.2 if k >= 8 else 0.3 if k >= 5 else 0.4), f'随机{k}'
    for word, v in sizes:
        if word + '范围' in e or ('圆形' + word) in e or (word == '全屏' and '全屏' in e):
            return 2.0 + v, '消除' + word
    if any(k in e for k in ('横列', '纵列', '纵向', '横向', '圆形', '扇形', '消除')):
        return 2.3, '消除'
    return 5.0, '辅助'


def _face(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def identify(team_img, table=None):
    """队伍选择页 → 3 个角色（表里的行）。头像用灰度模板匹配，彩框/白框看卡片底部彩虹边。"""
    table = table or load_table()
    g = _face(team_img)
    out = []
    for cx in CARD_X:
        card = g[890:1050, cx - 80:cx + 80]
        best = (-1, None)
        for r in table:
            p = cv2.imread(r['img'])
            if p is None:
                continue
            face = _face(p)[15:150, 20:150]
            for sc in (0.78, 0.86, 0.94):
                t = cv2.resize(face, None, fx=sc, fy=sc)
                if t.shape[0] > card.shape[0] or t.shape[1] > card.shape[1]:
                    continue
                v = cv2.minMaxLoc(cv2.matchTemplate(card, t, cv2.TM_CCOEFF_NORMED))[1]
                if v > best[0]:
                    best = (v, r)
        r = best[1]
        if r:
            rainbow = is_rainbow(team_img, cx)
            # 同一角色的白/彩版本由边框决定
            same = [x for x in table if x['name'].rstrip('R') == r['name'].rstrip('R')]
            want = '彩' if rainbow else '白'
            r = next((x for x in same if x['frame'] == want), r)
        out.append(dict(r or {}, score=round(best[0], 2)))
    return out


def is_rainbow(img, cx):
    """彩框（レア）版本：卡片「Lv」那一条是彩虹渐变；白框版是单一黄色"""
    h = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    s = h[1030:1062, cx - 72:cx + 72].reshape(-1, 3)
    s = s[(s[:, 1] > 60) & (s[:, 2] > 150)]
    if len(s) < 300:
        return False
    hist = np.bincount(s[:, 0] // 15, minlength=12)
    return (hist > len(s) * 0.06).sum() >= 4
