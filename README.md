# 婶婶自动行军

《刀剣乱舞ぱずぎり》（iOS / Android）的 Mac 自动刷关脚本。它会自动选关、选队、连线消除、放奥义、乱舞扫色、清火焰泡泡、用炸弹，打完统计胜负和掉落。

除了普通关卡，也支持活动：大讨伐（按泡泡分值连线）和 scenario（地獄めぐり：可以指定关卡，也可以按顺序把所有关卡推完，剧情自动跳过）。

> ⚠️ 自动化脚本违反游戏的用户协议，使用有封号风险，请自行承担。仅供个人学习研究。

## 支持的设备

| 设备 | 截图 | 点击 / 拖动 | 是否占鼠标 |
|---|---|---|---|
| BlueStacks Air（推荐） | adb 原始截图 | adb + 直接写虚拟触摸设备 | 不占用，可以后台挂机 |
| iPhone 镜像（macOS 自带） | 窗口截图 | 真实鼠标 | 占用，镜像窗口会被切到前台 |

---

## 安装步骤

### 0. 需要准备

- **Apple 芯片（M1 及以后）的 Mac**，macOS 14 或更新。
- 两种玩法任选其一：
  - **BlueStacks Air**（Mac 版安卓模拟器），在里面装游戏。
  - **iPhone 镜像**：macOS 15 以上，iPhone 系统 iOS 18 以上，并且 iPhone 上已经装好游戏。
- 大约 3 GB 硬盘空间（conda 和 Python 库）。

### 1. 安装 Xcode 命令行工具

用来编译 App 和截图、点击、文字识别等小工具。打开「终端」，运行：

```bash
xcode-select --install
```

在弹出的窗口里点「安装」，等它装完。已经装过的话会提示 `already installed`，直接下一步。

检查一下：

```bash
swiftc --version
```

能显示版本号就可以了。

### 2. 安装 conda（Miniconda）

用来装一个独立的 Python 环境，不影响系统自带的 Python。

1. 打开 <https://docs.anaconda.com/miniconda/>，下载 **macOS Apple M1 (arm64)** 的 `.pkg` 安装包，双击安装。
   - 有 Homebrew 的话，也可以用这一行代替：`brew install --cask miniconda`
2. 装完后**关掉终端再重新打开**，运行：

   ```bash
   conda init zsh
   ```

3. 再关掉终端重新打开，运行 `conda --version`，能显示版本号就可以了。

### 3. 下载本项目

建议放在「文稿」之类的普通文件夹里。在终端里运行：

```bash
cd ~/Documents
git clone https://github.com/Zaoziiii/shenshen-auto-march.git
cd shenshen-auto-march
```

以后的命令都在这个文件夹里运行。

### 4. 建 Python 环境

环境名必须叫 `pazugiri`，编译 App 时会按这个名字去找。

```bash
conda create -n pazugiri python=3.11 -y
conda activate pazugiri
pip install opencv-python-headless numpy pillow
```

检查一下：

```bash
python -c "import cv2, numpy; print('ok', cv2.__version__)"
```

能显示 `ok` 就可以了。

### 5. 编译小工具和 App

```bash
./make_tools.sh
./build_app.sh
```

- `make_tools.sh` 编译截图、点击、拖动、文字识别（macOS 自带的 Vision）、窗口定位这些小工具，最后显示 `done`。
- `build_app.sh` 编译图形界面「ぱずぎり挂机.app」并装到「应用程序」文件夹，会显示它找到的项目路径和 Python 路径。
  - 提示「找不到 conda 环境 pazugiri 里的 python」时，先确认第 4 步做完了；也可以手动指定：

    ```bash
    PAZ_PY=$(conda run -n pazugiri which python) ./build_app.sh
    ```

  - 项目文件夹以后挪了位置，要重新运行一次 `./build_app.sh`。

### 6. 准备游戏设备

#### 方式 A：BlueStacks Air（推荐，可后台挂机）

1. 从 <https://www.bluestacks.com/> 下载 **BlueStacks Air**（Apple 芯片版），安装后打开。
2. 在 BlueStacks 里登录 Google 账号，装好《刀剣乱舞ぱずぎり》，进游戏把新手教程走完。
3. 打开 BlueStacks 的「设置 → 高级」，打开 **「Android 调试（ADB）」**，地址是 `127.0.0.1:5555`。
4. 确认 adb 连得上（显示 `127.0.0.1:5555 device` 就对了）：

   ```bash
   /Applications/BlueStacks.app/Contents/MacOS/hd-adb connect 127.0.0.1:5555
   /Applications/BlueStacks.app/Contents/MacOS/hd-adb devices
   ```

注意：
- 分辨率保持默认的 **1080×1920**。
- **不要**在游戏运行时改分辨率，也**不要**打开「输入调试」。否则游戏会报「致命なエラー（9-999）」，只能重装游戏。
- 挂机时 BlueStacks 窗口可以放在后面，不占鼠标，Mac 可以照常用。

#### 方式 B：iPhone 镜像

1. Mac 和 iPhone 登录同一个 Apple ID，打开 Mac 上的「iPhone 镜像」App，按提示连上 iPhone。
2. 在镜像窗口里打开游戏。
3. 挂机时脚本会用真实鼠标点镜像窗口，并把它切到前台，所以**挂机期间不要用这台 Mac**。

### 7. 打开 App 并授权

1. 打开「应用程序」里的 **「ぱずぎり挂机」**。
2. 第一次点「开始」时，App 会弹出授权提示。按提示打开「系统设置 → 隐私与安全性」：
   - **辅助功能**：打开「ぱずぎり挂机」，没有它点击不了游戏。
   - **屏幕与系统录音**（旧版系统叫「屏幕录制」）：打开「ぱずぎり挂机」。
3. 授权后**退出 App（⌘Q）再重新打开**，权限才会生效。

> 每次重新运行 `./build_app.sh` 后，系统可能认为这是一个新 App，权限会失效。如果点「开始」后游戏没反应，日志提示没有权限，就到上面两个地方把「ぱずぎり挂机」删掉（选中后点「−」）再重新加一次。

---

## 使用

打开「ぱずぎり挂机」，按顺序选：

| 选项 | 说明 |
|---|---|
| 设备 | BlueStacks Air 或 iPhone 镜像 |
| 刷什么 | **普通关卡**：填「章-话」，如 `3-29`<br>**大讨伐活动**：不用填关卡，用活动票（不会买票）<br>**scenario**：地獄めぐり活动，填「地图-关」，如 `3-2`。还没解锁的话，先一关一关推过去（剧情小关自动跳过） |
| 队伍 | 队名，或者第几队（1~5）。留空就用当前队伍 |
| 乱舞保留色 | 乱舞时间留着不扫的颜色。「自动」= 按队伍奥义需要的颜色。大讨伐自动保留首领的颜色 |
| 刷关方式 | 刷到心用完 / 刷够指定次数。scenario 还有「**顺序解锁所有关卡**」：从第一个没打过的关开始推，全部解锁后停止 |
| 心用完后 | 停止 / 等心恢复 / 用 50 宝玉补 10 颗心 |
| 其他 | 打完自动关游戏、延迟开始、每隔几小时再刷一轮 |

点「开始」就开始挂机。运行中在任何程序里按 **⌃C（control + C）** 停止。

- 输了不会用宝玉复活，直接撤退。
- 中途重开游戏、有没打完的战斗时，会点「再開する」接着打。
- 换天弹窗、登录奖励、日报都会自动处理。

日志写在项目文件夹里的 `farm.log`。走不到关卡时，最后的画面会存成 `refs/nav_fail_*.png`。

**同一时间只开一个脚本。** App 在跑的时候，不要再从终端运行 `farm.py`，两个脚本会同时点游戏。

不用 App、直接在终端跑也可以：

```bash
conda activate pazugiri
PAZ_DEVICE=bluestacks python pz/farm.py ui_config.json
```

`ui_config.json` 是 App 每次点「开始」时写出的设置文件，格式见 `pz/farm.py` 开头的说明。

## 更新

```bash
cd ~/Documents/shenshen-auto-march
git pull
./make_tools.sh
./build_app.sh
```

然后退出 App（⌘Q）再重新打开。

## 常见问题

| 现象 | 处理 |
|---|---|
| 点「开始」后游戏没反应 | 检查第 7 步的两个权限；重新编译过的话，把权限删掉再加一次 |
| BlueStacks 模式提示连不上 / 截图失败 | 确认 BlueStacks 开着、ADB 打开了，用第 6 步的 `hd-adb devices` 看一下 |
| 游戏报 9-999 | BlueStacks 里改过分辨率或开了输入调试，改回来后重装游戏 |
| 卡在某个画面不动 | 看 `farm.log` 最后几行和 `refs/nav_fail_*.png`，多半是新出现的弹窗还没适配 |
| App 打不开，提示「已损坏」或「无法验证开发者」 | App 是本机编译、本地签名的，到「系统设置 → 隐私与安全性」最下面点「仍要打开」 |

---

## 代码结构

| 文件 | 作用 |
|---|---|
| `pz/farm.py` | 刷关主循环：导航 → 戦う → 对战 → 结算，统计胜负、掉落、用时 |
| `pz/play.py` | 对战：选链、连线（发白区域重算 + 松手前核对计数）、奥义优先级、炸弹、火焰回合、乱舞横扫、死亡撤退 |
| `pz/board.py` / `flame.py` / `bombs.py` / `obstacles.py` | 泡泡（含活动的大小泡泡）、火焰泡泡、炸弹、贝壳/箱子识别 |
| `pz/solver.py` | 最长（活动关：分值最高）同色链、按队伍奥义颜色选链、火焰分块 |
| `pz/whiten.py` / `count.py` | 连线时的发白区域、连接计数读取 |
| `pz/nav.py` | 选关、切章节、选队、活动导航、读心数/票数和掉落、各种弹窗、开关游戏、宝玉补体力 |
| `pz/chars.py` | 认队伍角色（`角色技能.md` 头像表）和奥义优先级 |
| `adbin.py` / `rawtouch.py` | BlueStacks 的 adb 输入和快速触摸 |
| `g.sh` / `*.swift` | 截图、点击、拖动、OCR（macOS Vision）、窗口定位等小工具 |
| `app/` | SwiftUI 界面（`build_app.sh` 编译） |
| `需求.md` | 完整的需求和实测记录 |
| `活动算法.md` / `scenario活动.md` | 大讨伐、scenario 活动的设计说明 |
| `角色技能.md` | 角色奥义对照表 |

识别统一在 708×1562 的「iPhone 标准画面」坐标里做。BlueStacks 画面按 `x' = 1.596x − 26, y' = 1.596y − 330` 换算（见 `adbin.py`）。
