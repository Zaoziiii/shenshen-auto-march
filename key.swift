import CoreGraphics
import Foundation
// usage: key <keycode> [cmd]   给前台程序发一个按键
let a = CommandLine.arguments
let code = CGKeyCode(Int(a[1])!)
let src = CGEventSource(stateID: .hidSystemState)
let d = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: true)!
let u = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: false)!
if a.count > 2 && a[2] == "cmd" { d.flags = .maskCommand; u.flags = .maskCommand }
d.post(tap: .cghidEventTap); usleep(80000); u.post(tap: .cghidEventTap)
