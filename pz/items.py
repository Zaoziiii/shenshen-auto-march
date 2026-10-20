"""物品图鉴：从「アイテム一覧」截图里提取 图标 + 名字，存到 pz/items/。
之后统计掉落时，用图标比对认出是哪个物品。"""
import json, subprocess, sys
from pathlib import Path
import cv2, numpy as np

ROOT = Path(__file__).parent.parent
OUT = Path(__file__).parent / 'items'
COLS = [115, 268, 420, 573]       # 4 列图标圆心 x（2x 像素）
R = 58                            # 图标圆底半径


def ocr(path):
    out = subprocess.run([str(ROOT / 'ocr'), str(path)], capture_output=True, text=True).stdout
    res = []
    for line in out.splitlines():
        x, y, w, h, *t = line.split(' ')
        res.append((int(x), int(y), int(w), int(h), ' '.join(t)))
    return res


def extract(paths, tab, catalog=None):
    """以 OCR 读到的名字为准：名字中心对齐到最近的列，图标圆心在名字上方约 82px"""
    OUT.mkdir(exist_ok=True)
    catalog = {} if catalog is None else catalog
    for p in paths:
        img = cv2.imread(str(p))
        for x, y, w, h, t in ocr(p):
            cx = min(COLS, key=lambda c: abs(c - (x + w / 2)))
            if abs(cx - (x + w / 2)) > 60 or t.isdigit() or not (520 < y < 1200) or h > 26:
                continue
            cy = y - 82
            if cy - 50 < 440 or t in catalog:
                continue
            icon = img[cy - 45:cy + 40, cx - 45:cx + 35]      # 避开右下角数量数字
            f = OUT / f'{tab}_{sum(1 for v in catalog.values() if v["tab"] == tab):02d}.png'
            cv2.imwrite(str(f), icon)
            catalog[t] = {'tab': tab, 'icon': f.name}
    return catalog


if __name__ == '__main__':
    tab = sys.argv[1]
    cat = extract(sorted(Path(sys.argv[2]).glob('*.png'), key=lambda p: int(p.stem[1:])), tab)
    print(json.dumps(cat, ensure_ascii=False, indent=1))
    print(len(cat))


def capture_tab(tab, tab_xy, max_pages=20):
    """切到某个标签，从顶部开始逐行滚动截图，直到画面不再变化"""
    G = str(ROOT / 'g.sh')
    d = ROOT / 'refs' / 'items' / tab
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run([G, 'tap', *map(str, tab_xy)]); subprocess.run(['sleep', '1.5'])
    for _ in range(3):
        subprocess.run([G, 'drag', '355', '560', '355', '900', '355', '1150']); subprocess.run(['sleep', '0.6'])
    subprocess.run(['sleep', '1'])
    prev = None
    for i in range(1, max_pages + 1):
        f = d / f'g{i}.png'
        subprocess.run([G, 'shot', f'items/{tab}/g{i}'])
        cur = cv2.imread(str(f))[440:1200]
        if prev is not None and cv2.absdiff(cur, prev).mean() < 2:
            f.unlink(); break
        prev = cur
        subprocess.run([G, 'drag', '355', '1000', '355', '900', '355', '800', '355', '800', '355', '800'])
        subprocess.run(['sleep', '1.2'])
    return sorted(d.glob('g*.png'), key=lambda p: int(p.stem[1:]))
