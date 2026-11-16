#!/bin/zsh
# 重新编译「ぱずぎり挂机.app」（在临时目录签名再拷回来，避开 iCloud 文件夹的签名问题）
# app/main.swift 里的项目路径（ROOT）和 Python 路径（PY）在这里按本机自动填进去：
#   ROOT = 这个脚本所在的文件夹
#   PY   = 环境变量 PAZ_PY；没设就找 conda 环境「pazugiri」里的 python
cd "${0:A:h}"
ROOT_DIR=${0:A:h}
PY=${PAZ_PY:-}
if [[ -z $PY ]]; then
  for c in conda ~/miniconda3/bin/conda ~/anaconda3/bin/conda ~/miniforge3/bin/conda /opt/anaconda3/bin/conda \
           /opt/miniconda3/bin/conda /opt/homebrew/Caskroom/miniconda/base/bin/conda /opt/homebrew/Caskroom/miniforge/base/bin/conda; do
    if command -v $c >/dev/null 2>&1; then
      PY=$($c run -n pazugiri python -c 'import sys; print(sys.executable)' 2>/dev/null) && [[ -x $PY ]] && break
      PY=
    fi
  done
fi
if [[ -z $PY || ! -x $PY ]]; then
  echo "找不到 conda 环境 pazugiri 里的 python。请先按 README 建好环境，或者用 PAZ_PY=/path/to/python ./build_app.sh 指定。"
  exit 1
fi
echo "项目路径：$ROOT_DIR"
echo "Python：  $PY"

B=$(mktemp -d)/build; mkdir -p "$B/ぱずぎり挂机.app/Contents/MacOS"
sed -e "s|^let ROOT = .*|let ROOT = \"$ROOT_DIR\"|" -e "s|^let PY = .*|let PY = \"$PY\"|" app/main.swift > "$B/main.swift"
swiftc -O -parse-as-library -target arm64-apple-macos14.0 "$B/main.swift" -o "$B/ぱずぎり挂机.app/Contents/MacOS/pazugiri" || exit 1
cp app/Info.plist "$B/ぱずぎり挂机.app/Contents/Info.plist"
mkdir -p "$B/ぱずぎり挂机.app/Contents/Resources"; cp app/AppIcon.icns "$B/ぱずぎり挂机.app/Contents/Resources/AppIcon.icns"
codesign --force --deep -s - "$B/ぱずぎり挂机.app"
# 编译后直接替换「应用程序」里的版本
DEST="/Applications/ぱずぎり挂机.app"
rm -rf "$DEST"; ditto "$B/ぱずぎり挂机.app" "$DEST"
echo done
