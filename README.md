# 婶婶自动行军

《刀剣乱舞ぱずぎり》（iOS / Android）的 Mac 自动刷关脚本：自动选关、选队、连线消除、放奥义、乱舞扫色、清火焰泡泡、用炸弹，打完统计胜负和掉落。

> ⚠️ 自动化脚本违反游戏的用户协议，使用有封号风险，请自行承担。仅供个人学习研究。

## 支持的设备

| 设备 | 截图 | 点击 / 拖动 | 是否占鼠标 |
|---|---|---|---|
| iPhone 镜像（macOS 自带） | 窗口截图 | 真实鼠标 | 占用，镜像窗口会被切到前台 |
| BlueStacks Air（Apple 芯片 Mac） | adb 原始截图 | adb + 直接写虚拟触摸设备 | 不占用，可以后台挂机 |

BlueStacks 注意事项：
- 分辨率保持默认 1080×1920；**不要**在游戏运行时改分辨率，也不要打开「输入调试」，否则游戏会报「致命なエラー（9-999）」，只能重装。
- 设置里打开「Android 调试（ADB）」（127.0.0.1:5555）。
- 识别统一在 708×1562 的「iPhone 标准画面」坐标里做，BlueStacks 画面按 `x' = 1.596x − 26, y' = 1.596y − 330` 换算（见 `adbin.py`）。

## 安装

需要 Apple 芯片的 Mac、Xcode 命令行工具、conda。

```bash
conda create -n pazugiri python=3.11
conda activate pazugiri
pip install opencv-python-headless numpy pillow
./make_tools.sh      # 编译 Swift 小工具
./build_app.sh       # 编译「ぱずぎり挂机.app」并装到「应用程序」
```

`app/main.swift` 和 `g.sh` 里写死了项目路径和 Python 路径，换电脑要改一下。

第一次用 iPhone 镜像模式时，要在「系统设置 → 隐私与安全性」里给「ぱずぎり挂机」开「辅助功能」和「屏幕录制」。

## 使用

打开「ぱずぎり挂机」：选设备、关卡（如 `3-29`）、队伍（队名或 1~5）、乱舞保留色（自动 = 按队伍奥义），刷到心用完或刷够指定次数（可选心用完后停止 / 等心恢复 / 用 50 宝玉补 10 颗心），可设延迟开始和定时重复。运行中在任何程序里按 **⌃C** 停止。

日志写在 `farm.log`，出错时截图存在 `refs/`。

也可以直接跑：

```bash
PAZ_DEVICE=bluestacks python pz/farm.py ui_config.json
```

## 代码结构

| 文件 | 作用 |
|---|---|
| `pz/farm.py` | 刷关主循环：导航 → 戦う → 对战 → 结算，统计胜负、掉落、用时 |
| `pz/play.py` | 对战：选链、连线（发白区域重算 + 松手前核对计数）、奥义优先级、炸弹、火焰回合、乱舞横扫、死亡撤退 |
| `pz/board.py` / `flame.py` / `bombs.py` | 泡泡、火焰泡泡、炸弹识别 |
| `pz/solver.py` | 最长同色链、按队伍奥义颜色选链、火焰分块 |
| `pz/whiten.py` / `count.py` | 连线时的发白区域、连接计数读取 |
| `pz/nav.py` | 选关、切章节、选队、读心数和掉落、开关游戏、宝玉补体力 |
| `pz/chars.py` | 认队伍角色（`角色技能.md` 头像表）和奥义优先级 |
| `adbin.py` / `rawtouch.py` | BlueStacks 的 adb 输入和快速触摸 |
| `g.sh` / `*.swift` | 截图、点击、拖动、OCR（macOS Vision）、窗口定位等小工具 |
| `app/` | SwiftUI 界面 |
| `需求.md` | 完整的需求和实测记录 |
| `角色技能.md` | 角色奥义对照表 |
