import CoreGraphics
let p = CGEvent(source: nil)!.location
CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: p, mouseButton: .left)?.post(tap: .cghidEventTap)
print(p)
