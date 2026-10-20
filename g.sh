#!/bin/zsh
# helper: g.sh tap px py | g.sh drag px1 py1 px2 py2 ... | g.sh shot name | g.sh focus
# 坐标统一按「708×1562 的标准截图」写；按当前画面实际大小换算成屏幕点。
# 设备由环境变量 PAZ_DEVICE 决定：iphone（默认，iPhone 镜像）或 bluestacks（BlueStacks Air）
D=${0:A:h}
DEV=${PAZ_DEVICE:-iphone}
if [[ $DEV == bluestacks ]]; then
  WIN=$D/winbs; APPNAME="BlueStacks"; FRONT_MATCH="BlueStacks"
else
  WIN=$D/win; APPNAME="iPhone Mirroring"; FRONT_MATCH="iPhone"
fi
read ID X Y W H <<<"$($WIN | awk 'NR==1{id=$1} /X =/{gsub(/[";]/,"");x=$3} /Y =/{gsub(/[";]/,"");y=$3} /Width =/{gsub(/[";]/,"");w=$3} /Height =/{gsub(/[";]/,"");h=$3} END{print id,x,y,w,h}')"
SX=$(( W / 708.0 )); SY=$(( H / 1562.0 ))

bring_front() {
  # 确认目标真的在前台再点（别的程序在前台时点击会丢）
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    lsappinfo info -only name "$(lsappinfo front)" | grep -q "$FRONT_MATCH" && break
    open -a "$APPNAME"; sleep 0.3
  done
}

cmd=$1; shift
case $cmd in
  focus) [[ $DEV == bluestacks ]] || bring_front;;
  shot)
    if [[ $DEV == bluestacks ]]; then
      # 截图走 adb（后台、不占鼠标）
      /Applications/BlueStacks.app/Contents/MacOS/hd-adb -s 127.0.0.1:5555 exec-out screencap -p > "$D/refs/$1.png"
    else
      screencapture -x -o -l$ID "$D/refs/$1.png"
    fi;;
  tap|drag|fast)
    if [[ $DEV == bluestacks ]]; then
      # BlueStacks：adb 后台输入，坐标直接用标准截图坐标（adbin.py 内部换算）
      /usr/bin/python3 $D/adbin.py $([[ $cmd == drag ]] && echo path || echo $cmd) "$@"
      exit 0
    fi
    bring_front
    sleep 0.15
    args=(); i=0
    for v in "$@"; do if (( i % 2 == 0 )); then args+=$(( X + v*SX )); else args+=$(( Y + v*SY )); fi; ((i++)); done
    [[ $cmd == tap ]] && $D/input tap $args || $D/input $([[ $cmd == fast ]] && echo fast || echo path) $args;;
esac
