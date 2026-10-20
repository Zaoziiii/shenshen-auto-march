import CoreGraphics
import Foundation
// usage: sweep step_px usleep_per_step x1 y1 x2 y2 ...   按下 x1,y1，沿折线按固定步长匀速拖动，最后松开
let a = CommandLine.arguments.dropFirst().compactMap { Double($0) }
let step = a[0], us = useconds_t(a[1])
var pts: [CGPoint] = []; var i = 2
while i + 1 < a.count { pts.append(CGPoint(x: a[i], y: a[i+1])); i += 2 }
func post(_ t: CGEventType, _ p: CGPoint) { CGEvent(mouseEventSource: nil, mouseType: t, mouseCursorPosition: p, mouseButton: .left)?.post(tap: .cghidEventTap) }
post(.mouseMoved, pts[0]); usleep(20000); post(.leftMouseDown, pts[0]); usleep(50000)
var cur = pts[0]
for p in pts.dropFirst() {
  let d = hypot(p.x - cur.x, p.y - cur.y); let n = max(1, Int(d / step))
  for s in 1...n { let t = Double(s) / Double(n); post(.leftMouseDragged, CGPoint(x: cur.x + (p.x - cur.x) * t, y: cur.y + (p.y - cur.y) * t)); usleep(us) }
  cur = p
}
usleep(40000); post(.leftMouseUp, cur)
