"""刷关主程序（UI 调用它）。
python pz/farm.py config.json
config: {"stage": "3-29", "team": "Trans" 或 "1", "keep": "auto"/"red"/..., 
         "count": 0(=刷到心用完) 或 N, "heart_out": "stop"/"wait"/"buy"}"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import play, nav, chars

ROOT = Path(__file__).parent.parent
STATUS = ROOT / 'status.json'
log = nav.log


def auto_keep(team):
    """乱舞保留色：队里有转色奥义就留它转成的颜色，否则留队伍奥义最需要的颜色"""
    for c in team:
        o = c.get('ougi', '')
        for k, col in (('・赤', 'red'), ('・青', 'blue'), ('・黄', 'yellow')):
            if '色変幻' in o and k in o:
                return col
        if 'くちなし' in o:
            return 'yellow'
    cols = [c.get('color') for c in team if c.get('color')]
    return max(set(cols), key=cols.count) if cols else 'red'


def save_status(**kw):
    STATUS.write_text(json.dumps(kw, ensure_ascii=False, indent=1))


def wait_for_heart(stage, team):
    log('心用完了，等心恢复（每 3 分钟看一次）…')
    while True:
        for _ in range(18):
            play.check_stop(); time.sleep(10)
        if nav.goto_team_select(stage, team) and nav.hearts(play.shot()) > 0:
            return True


def wait_minutes(minutes, why):
    if minutes <= 0:
        return
    end = time.time() + minutes * 60
    log(f'{why}：等 {minutes / 60:.1f} 小时，{time.strftime("%H:%M", time.localtime(end))} 开始')
    while time.time() < end:
        play.check_stop(); time.sleep(5)


def main_loop(cfg):
    """延迟开始 + 可选的每隔一段时间重复刷一轮"""
    (ROOT / 'STOP').unlink(missing_ok=True)
    try:
        wait_minutes(float(cfg.get('delay_min') or 0), '延迟开始')
        rnd = 1
        while True:
            log(f'####### 第 {rnd} 轮刷关 #######')
            main(cfg)
            every = float(cfg.get('repeat_min') or 0)
            if every <= 0 or (ROOT / 'STOP').exists():
                break
            rnd += 1
            wait_minutes(every, '等心恢复后再刷下一轮')
    except play.Stopped as e:
        log('已停止：', e)


def main(cfg):
    stage, team_sel = cfg['stage'], cfg.get('team') or None
    count, heart_out = int(cfg.get('count') or 0), cfg.get('heart_out', 'stop')
    win = lose = unknown = 0
    drops = {}
    play.board.THRESH = 0.55
    table = chars.load_table()
    k = 0
    nav_failed = False
    durations = []          # 每局用时（秒）
    t_round = [time.time()]

    def tally(r, label):
        nonlocal win, lose, unknown
        if r is None:
            t = nav.ocr(play.shot())
            if nav.find(t, '戦闘結果') or nav.find(t, '獲得報酬'):
                play.RESULT_IMGS.append(play.shot()); r = True
        got = {}
        for im in play.RESULT_IMGS:
            for name, n in nav.read_rewards(im).items():
                got[name] = max(got.get(name, 0), n)
        for name, n in got.items():
            drops[name] = drops.get(name, 0) + n
        if r is True: win += 1
        elif r is False: lose += 1
        else: unknown += 1
        d = time.time() - t_round[0]
        durations.append(d)
        log(f'--- {label}：{"胜" if r else "负" if r is False else "未知"}  用时 {int(d // 60)}分{int(d % 60):02d}秒  掉落：{got or "无"}')

    try:
        # 开始时已经在对战中（棋盘 / 乱舞 / 奥义选位置 / 结算 / 死亡弹窗）→ 先接着打完这一局
        img = play.shot()
        in_battle = (len(play.board.detect(img)) >= 25 or play.is_rush(img) or play.is_aim_screen(img)
                     or play.is_result(img) or play.is_continue_dialog(img) or play.is_retreat_dialog(img))
        if in_battle:
            keep = cfg.get('keep') or 'auto'
            keep = 'red' if keep == 'auto' else keep        # 中途接手读不到队伍卡片，自动模式先按红色
            log(f'检测到正在对战中，先接着打完这一局（乱舞留 {keep}）')
            play.RESULT_IMGS.clear()
            t_round[0] = time.time()
            k = 1
            tally(play.run(prefer=(keep,)), '第 1 局（中途接手）')
            time.sleep(2)
        while True:
            play.mark()
            if not nav.goto_team_select(stage, team_sel):
                log('走不到关卡', stage, '（或找不到队伍）'); nav_failed = True; break
            img = play.shot()
            team = chars.identify(img, table)
            play.TEAM = team
            keep = cfg.get('keep') or 'auto'
            keep = auto_keep(team) if keep == 'auto' else keep
            done = count > 0 and k >= count          # 指定次数已经刷够
            if nav.hearts(img) == 0:
                if done:
                    log(f'已刷够 {count} 次，心也用完了，结束'); break
                if count == 0 or heart_out == 'stop':
                    log('心用完了，停止'); break
                if heart_out == 'wait':
                    wait_for_heart(stage, team_sel); continue
                if heart_out == 'buy':
                    got = nav.buy_hearts()
                    if got == 'event':
                        log('活动体力用完了，停止'); break
                    if got:
                        continue
                    log('补充体力失败，停止'); nav_failed = True; break
            if done and k == count:
                log(f'已刷够 {count} 次，还有 {nav.hearts(img)} 颗心，继续刷完心再结束')
            k += 1
            log(f'=== 第 {k} 局 {stage}  队伍：{"、".join(c.get("name", "?") for c in team)}  乱舞留 {keep}  （剩 {nav.hearts(img)} 颗心）')
            save_status(running=True, stage=stage, round=k, win=win, lose=lose, unknown=unknown, drops=drops, team=[c.get('name') for c in team])
            play.RESULT_IMGS.clear()
            t_round[0] = time.time()
            play.tap(355, 1340); time.sleep(4)
            if nav.find(nav.ocr(play.shot()), '戦う'):     # 点了没反应 → 多半是点击被系统拦了
                log('点了「戦う」但画面没变：请检查「ぱずぎり挂机」的辅助功能权限，停止'); nav_failed = True; break
            time.sleep(3)
            r = play.run(prefer=(keep,))
            tally(r, f'第 {k} 局')
            save_status(running=True, stage=stage, round=k, win=win, lose=lose, unknown=unknown, drops=drops, team=[c.get('name') for c in team])
            time.sleep(2)
    except play.Stopped as e:
        log('已停止：', e)
        (ROOT / 'STOP').touch()
    summary = f'胜利 {win} 次，失败 {lose} 次' + (f'，结局不明 {unknown} 次' if unknown else '')
    if durations:
        avg = sum(durations) / len(durations)
        summary += f'\n每局平均 {int(avg // 60)}分{int(avg % 60):02d}秒（最快 {int(min(durations) // 60)}分{int(min(durations) % 60):02d}秒，最慢 {int(max(durations) // 60)}分{int(max(durations) % 60):02d}秒）'
    if drops:
        summary += '\n掉落：' + '、'.join(f'{n} {c} 个' for n, c in sorted(drops.items(), key=lambda kv: -kv[1]))
    log('===== 汇总 =====\n' + summary)
    save_status(running=False, round=k, win=win, lose=lose, unknown=unknown, drops=drops, summary=summary)
    if nav_failed:
        log('因为导航失败而结束：不关游戏，方便你看停在了哪个画面')
    elif cfg.get('close_game') and not (ROOT / 'STOP').exists():
        nav.close_game()


class _Tee:
    """对战部分的输出也一起写进 farm.log"""
    def __init__(self, stream, path):
        self.s, self.f = stream, open(path, 'a', encoding='utf-8')
    def write(self, x):
        self.s.write(x); self.f.write(x); self.f.flush()
    def flush(self):
        self.s.flush()


if __name__ == '__main__':
    import os
    _cfg0 = json.load(open(sys.argv[1])) if sys.argv[1].endswith('.json') else {}
    os.environ['PAZ_DEVICE'] = _cfg0.get('device', 'iphone')      # g.sh / touch.py 据此选设备
    sys.stdout = _Tee(sys.stdout, ROOT / 'farm.log')
    sys.stderr = _Tee(sys.stderr, ROOT / 'farm.log')          # 报错也写进日志
    print(f'\n==================== {time.strftime("%Y-%m-%d %H:%M:%S")} 开始（{os.environ["PAZ_DEVICE"]}）====================', flush=True)
    arg = sys.argv[1]
    cfg = json.load(open(arg)) if arg.endswith('.json') else {'stage': arg, 'count': int(sys.argv[2]) if len(sys.argv) > 2 else 0}
    # 卡住报警：60 秒没有任何日志输出，就把每个线程正在执行的代码位置写进 farm.log
    import faulthandler, threading
    _logf = open(ROOT / 'farm.log', 'a')
    _last = [time.time()]
    _orig_write = sys.stdout.write
    def _w(x):
        _last[0] = time.time(); return _orig_write(x)
    sys.stdout.write = _w
    def _watch():
        while True:
            time.sleep(10)
            if time.time() - _last[0] > 60:
                _logf.write(f'\n!!! {time.strftime("%H:%M:%S")} 60 秒没有进展，当前执行位置：\n'); _logf.flush()
                faulthandler.dump_traceback(file=_logf)
                _last[0] = time.time()
    threading.Thread(target=_watch, daemon=True).start()
    try:
        main_loop(cfg)
    except Exception:
        import traceback
        log('脚本出错：\n' + traceback.format_exc())
        cv2_img = play.shot()
        if cv2_img is not None:
            import cv2
            cv2.imwrite(str(ROOT / 'refs' / f'crash_{int(time.time())}.png'), cv2_img)
        raise
