import SwiftUI
import AppKit
import ApplicationServices

// 这两行由 build_app.sh 编译时按本机自动替换（项目文件夹、conda 环境 pazugiri 的 python），不用手改
let ROOT = "/path/to/pazugiri"
let PY = "/path/to/conda/envs/pazugiri/bin/python"

final class Runner: ObservableObject {
    @Published var log = ""
    @Published var running = false
    @Published var summary = ""
    @Published var progress = ""     // 「已打 N 局」：每 2 秒读一次 status.json（farm.py 每局开始和结束都会写）
    var proc: Process?
    var monitors: [Any] = []

    func readProgress() {
        guard let d = try? Data(contentsOf: URL(fileURLWithPath: ROOT + "/status.json")),
              let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return }
        let w = j["win"] as? Int ?? 0, l = j["lose"] as? Int ?? 0, u = j["unknown"] as? Int ?? 0
        let done = w + l + u, round = j["round"] as? Int ?? 0
        let stage = (j["stage"] as? String).map { $0 + "  " } ?? ""
        var s = "\(stage)已打 \(done) 局（胜 \(w)  负 \(l)" + (u > 0 ? "  不明 \(u)" : "") + "）"
        if (j["running"] as? Bool ?? false) && running && round > done { s += "  ·  正在打第 \(round) 局" }
        if let dr = j["drops"] as? [String: Int], !dr.isEmpty {
            s += "\n掉落：" + dr.sorted { $0.value > $1.value }.map { "\($0.key) \($0.value)" }.joined(separator: "、")
        }
        if s != progress { progress = s }
    }

    init() {
        // 紧急停止：⌃C（control+C）。全局监听（在别的程序里按也生效，需要辅助功能权限）+ 本窗口监听
        let isStop: (NSEvent) -> Bool = { e in
            e.modifierFlags.intersection(.deviceIndependentFlagsMask).contains(.control) && e.charactersIgnoringModifiers?.lowercased() == "c"
        }
        if let g = NSEvent.addGlobalMonitorForEvents(matching: .keyDown, handler: { e in
            if isStop(e) { DispatchQueue.main.async { if self.running { self.stop() } } }
        }) { monitors.append(g) }
        if let l = NSEvent.addLocalMonitorForEvents(matching: .keyDown, handler: { e in
            if isStop(e) && self.running { self.stop(); return nil }
            return e
        }) { monitors.append(l) }
        // 再加一层轮询：直接读键盘状态（不依赖辅助功能权限）
        Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { _ in self.readProgress() }
        Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { _ in
            guard self.running else { return }
            let c = CGEventSource.keyState(.combinedSessionState, key: 8)          // kVK_ANSI_C
            let cmd = CGEventSource.flagsState(.combinedSessionState).contains(.maskControl)
            if c && cmd && !FileManager.default.fileExists(atPath: ROOT + "/STOP") { self.stop() }
        }
    }

    func start(_ cfg: [String: Any]) {
        // 没有辅助功能权限时，系统会悄悄丢掉点击 → 先检查，弹出授权提示
        let opts = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        if !AXIsProcessTrustedWithOptions(opts) {
            log = "⚠️ 还没有「辅助功能」权限，脚本点不了游戏。\n请在 系统设置 → 隐私与安全性 → 辅助功能 里打开「ぱずぎり挂机」，然后退出 App 重新打开再点开始。\n"
            NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")!)
            return
        }
        if !CGPreflightScreenCaptureAccess() {
            CGRequestScreenCaptureAccess()
            log = "⚠️ 还没有「屏幕录制」权限。请在 系统设置 → 隐私与安全性 → 屏幕与系统录音 里打开「ぱずぎり挂机」，然后重开 App。\n"
            return
        }
        let cfgURL = URL(fileURLWithPath: ROOT + "/ui_config.json")
        if let d = try? JSONSerialization.data(withJSONObject: cfg, options: .prettyPrinted) { try? d.write(to: cfgURL) }
        try? FileManager.default.removeItem(atPath: ROOT + "/STOP")
        let p = Process()
        p.executableURL = URL(fileURLWithPath: PY)
        p.arguments = ["-u", "pz/farm.py", cfgURL.path]
        p.currentDirectoryURL = URL(fileURLWithPath: ROOT)
        let pipe = Pipe()
        p.standardOutput = pipe; p.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { h in
            let s = String(decoding: h.availableData, as: UTF8.self)
            guard !s.isEmpty else { return }
            DispatchQueue.main.async {
                self.log += s
                if self.log.count > 60000 { self.log = String(self.log.suffix(40000)) }
                if let r = s.range(of: "===== 汇总 =====\n") { self.summary = String(s[r.upperBound...]).trimmingCharacters(in: .whitespacesAndNewlines) }
            }
        }
        p.terminationHandler = { _ in DispatchQueue.main.async { self.running = false } }
        do {
            try p.run(); proc = p; running = true; summary = ""; log = ""
            let c = Process(); c.executableURL = URL(fileURLWithPath: "/usr/bin/caffeinate")
            c.arguments = ["-dims", "-w", String(p.processIdentifier)]          // 脚本运行期间不让 Mac 睡眠
            try? c.run()
        } catch { log += "启动失败：\(error)\n" }
    }

    func stop() {
        log += "\n>>> 收到停止，等当前这一步做完…\n"
        FileManager.default.createFile(atPath: ROOT + "/STOP", contents: Data())
        // 20 秒后还没停才强行结束 —— 只结束「这一次」的脚本（之前用 self.proc：停止后马上重新开始，会把新开的那个杀掉）
        let p = proc
        DispatchQueue.main.asyncAfter(deadline: .now() + 20) { if let p = p, p.isRunning { p.terminate() } }
    }
}

struct ContentView: View {
    @StateObject var r = Runner()
    @AppStorage("device") var device = "iphone"
    @AppStorage("stage") var stage = "3-29"
    @AppStorage("kind") var kind = "normal"         // 刷什么：normal 普通关卡 / event 大讨伐活动 / scenario 活动（地獄めぐり）
    @AppStorage("scenarioStage") var scenarioStage = "3-2"   // scenario 的关卡单独记，不和普通关卡混
    var event: Bool { kind == "event" }
    @AppStorage("team") var team = ""
    @AppStorage("keep") var keep = "auto"
    @AppStorage("mode") var mode = 0
    @AppStorage("count") var count = 5
    @AppStorage("heartOut") var heartOut = "stop"
    @AppStorage("closeGame") var closeGame = false
    @AppStorage("delayH") var delayH = 0.0
    @AppStorage("repeatH") var repeatH = 0.0

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Form {
                Picker("设备", selection: $device) {
                    Text("iPhone 镜像").tag("iphone"); Text("BlueStacks Air").tag("bluestacks")
                }.pickerStyle(.segmented)
                Picker("刷什么", selection: $kind) {
                    Text("普通关卡").tag("normal"); Text("大讨伐活动").tag("event"); Text("scenario").tag("scenario")
                }.pickerStyle(.segmented)
                    .help("大讨伐活动：按泡泡分值连线、乱舞保留首领颜色、用活动票。scenario：地獄めぐり活动，关卡没解锁时先按顺序推（剧情自动跳过）")
                if kind == "normal" {
                    TextField("关卡（章-话）", text: $stage).help("例如 3-29")
                }
                if kind == "scenario" && mode != 2 {
                    TextField("关卡（地图-关）", text: $scenarioStage).help("例如 3-2。还没解锁的话，先一关一关推过去（剧情小关自动跳过），解锁后就一直刷这一关")
                }
                TextField("队伍（队名或 1~5，空=当前队）", text: $team)
                if !event {
                    Picker("乱舞保留色", selection: $keep) {
                        Text("自动（按队伍奥义）").tag("auto"); Text("红").tag("red"); Text("黄").tag("yellow"); Text("绿").tag("green"); Text("蓝").tag("blue")
                    }
                } else {
                    Text("乱舞保留色：自动（首领的颜色）").foregroundStyle(.secondary)
                }
                Picker("刷关方式", selection: $mode) {
                    Text(event ? "刷到活动票用完" : "刷到心用完").tag(0); Text("刷够指定次数").tag(1)
                    if kind == "scenario" { Text("顺序解锁所有关卡").tag(2) }
                }
                    .pickerStyle(.segmented)
                    .onChange(of: kind) { if kind != "scenario" && mode == 2 { mode = 0 } }
                if mode == 2 && kind == "scenario" {
                    Text("从第一个没打过的关开始一关一关推（剧情小关自动跳过），全部解锁后停止").font(.caption).foregroundStyle(.secondary)
                }
                if mode == 1 && event {
                    Stepper("次数：\(count)（票先用完也会停）", value: $count, in: 1...999)
                }
                if mode == 1 && !event {
                    Stepper("次数：\(count)", value: $count, in: 1...999)
                }
                if (mode == 1 && !event) || (mode == 2 && kind == "scenario") {
                    Picker("心用完后", selection: $heartOut) {
                        Text("停止").tag("stop"); Text("等心恢复").tag("wait"); Text("用 50 宝玉补充 10 颗心").tag("buy")
                    }
                }
                Toggle("打完后自动关闭游戏", isOn: $closeGame)
                Stepper(delayH == 0 ? "延迟开始：不延迟" : String(format: "延迟开始：%.1f 小时后", delayH), value: $delayH, in: 0...12, step: 0.5)
                Stepper(repeatH == 0 ? "刷完后：不重复" : String(format: "刷完后每隔 %.1f 小时再刷一轮", repeatH), value: $repeatH, in: 0...12, step: 0.5)
            }
            HStack {
                Button(r.running ? "运行中…" : "开始") {
                    let unlockAll = kind == "scenario" && mode == 2
                    r.start(["device": device, "stage": event ? "大讨伐" : unlockAll ? "all" : kind == "scenario" ? scenarioStage : stage, "kind": kind,
                             "team": team, "keep": keep,
                             "count": mode == 1 ? count : 0, "heart_out": mode != 0 ? heartOut : "stop", "close_game": closeGame,
                             "delay_min": delayH * 60, "repeat_min": repeatH * 60])
                }.disabled(r.running).keyboardShortcut(.return)
                Button("停止（⌃C）") { r.stop() }.disabled(!r.running)
                Spacer()
                Text("运行中在任何程序里按 ⌃C（control+C）都会停止").font(.caption).foregroundStyle(.secondary)
            }
            if !r.progress.isEmpty {
                GroupBox("进度") { Text(r.progress).font(.title3).frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled) }
            }
            if !r.summary.isEmpty {
                GroupBox("汇总") { Text(r.summary).frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled) }
            }
            GroupBox("日志") {
                ScrollViewReader { sv in
                    ScrollView {
                        Text(r.log).font(.system(.caption, design: .monospaced))
                            .frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled).id("end")
                    }.onChange(of: r.log) { sv.scrollTo("end", anchor: .bottom) }
                }
            }
        }
        .padding(16).frame(minWidth: 460, minHeight: 560)
    }
}

@main
struct PazugiriApp: App {
    var body: some Scene { WindowGroup("ぱずぎり 挂机") { ContentView() } }
}
