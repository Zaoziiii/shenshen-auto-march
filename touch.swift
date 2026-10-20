import CoreGraphics
import Foundation
// 交互式触摸：从 stdin 读命令（屏幕点坐标）
//   down x y   按下
//   move x y   拖到（中间插 8 步）
//   up         松开
//   quit
setvbuf(stdout, nil, _IONBF, 0)
func post(_ t: CGEventType, _ p: CGPoint) { CGEvent(mouseEventSource: nil, mouseType: t, mouseCursorPosition: p, mouseButton: .left)?.post(tap: .cghidEventTap) }
var cur = CGPoint.zero
var pressed = false
while let line = readLine() {
  let f = line.split(separator: " ")
  guard let cmd = f.first else { continue }
  if cmd == "down", f.count == 3 {
    cur = CGPoint(x: Double(f[1])!, y: Double(f[2])!)
    post(.mouseMoved, cur); usleep(30000); post(.leftMouseDown, cur); pressed = true; usleep(60000)
  } else if (cmd == "move" || cmd == "slow"), f.count == 3 {
    let to = CGPoint(x: Double(f[1])!, y: Double(f[2])!)
    let n = cmd == "slow" ? 12 : 6
    for s in 1...n { let t = Double(s) / Double(n); post(.leftMouseDragged, CGPoint(x: cur.x + (to.x - cur.x) * t, y: cur.y + (to.y - cur.y) * t)); usleep(16000) }
    cur = to; usleep(cmd == "slow" ? 50000 : 18000)
  } else if cmd == "up" {
    usleep(60000); post(.leftMouseUp, cur); pressed = false
  } else if cmd == "quit" { break }
  print("ok")
}
// stdin 意外关闭（脚本被中断）时也要松开鼠标，免得一直按着
if pressed { post(.leftMouseUp, cur) }
