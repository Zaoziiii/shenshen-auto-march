import CoreGraphics
import Foundation
// usage: input tap x y | input path x1 y1 x2 y2 ... (screen points)
let a = CommandLine.arguments
func post(_ t: CGEventType, _ p: CGPoint) {
  CGEvent(mouseEventSource: nil, mouseType: t, mouseCursorPosition: p, mouseButton: .left)?.post(tap: .cghidEventTap)
}
let nums = a.dropFirst(2).compactMap { Double($0) }
var pts: [CGPoint] = []
var i = 0
while i + 1 < nums.count { pts.append(CGPoint(x: nums[i], y: nums[i+1])); i += 2 }
guard let first = pts.first else { exit(1) }
post(.mouseMoved, first); usleep(30000)
post(.leftMouseDown, first); usleep(60000)
if a[1] == "path" || a[1] == "fast" {
  var cur = first
  for p in pts.dropFirst() {
    let steps = a[1] == "fast" ? 3 : 8
    for s in 1...steps {
      let t = Double(s) / Double(steps)
      post(.leftMouseDragged, CGPoint(x: cur.x + (p.x - cur.x) * t, y: cur.y + (p.y - cur.y) * t))
      usleep(16000)
    }
    cur = p; usleep(a[1] == "fast" ? 35000 : 25000)
  }
  usleep(60000)
  post(.leftMouseUp, cur)
} else {
  post(.leftMouseUp, first)
}
