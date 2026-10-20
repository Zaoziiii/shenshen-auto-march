import CoreGraphics
// 输出 BlueStacks 里安卓画面所在的屏幕区域（格式和 win 一样：id + X/Y/Width/Height）
// BlueStacks Air 窗口：顶部 32pt 标题栏，右侧 32pt 工具栏，其余就是安卓画面
let l = CGWindowListCopyWindowInfo(.optionOnScreenOnly, kCGNullWindowID) as! [[String: Any]]
for w in l where (w["kCGWindowOwnerName"] as? String ?? "") == "BlueStacks" && (w["kCGWindowName"] as? String ?? "") == "BlueStacks Air" {
  let b = w["kCGWindowBounds"] as! [String: Any]
  let x = b["X"] as! Double, y = b["Y"] as! Double, ww = b["Width"] as! Double, wh = b["Height"] as! Double
  print(w["kCGWindowNumber"]!, "{")
  print("    Height = \(wh - 32);")
  print("    Width = \(ww - 32);")
  print("    X = \(x);")
  print("    Y = \(y + 32);")
  print("}")
  break
}
