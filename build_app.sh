#!/bin/zsh
# 重新编译「ぱずぎり挂机.app」（在临时目录签名再拷回来，避开 iCloud 文件夹的签名问题）
cd "${0:A:h}"
B=$(mktemp -d)/build; mkdir -p "$B/ぱずぎり挂机.app/Contents/MacOS"
swiftc -O -parse-as-library -target arm64-apple-macos14.0 app/main.swift -o "$B/ぱずぎり挂机.app/Contents/MacOS/pazugiri" || exit 1
cp app/Info.plist "$B/ぱずぎり挂机.app/Contents/Info.plist"
mkdir -p "$B/ぱずぎり挂机.app/Contents/Resources"; cp app/AppIcon.icns "$B/ぱずぎり挂机.app/Contents/Resources/AppIcon.icns"
codesign --force --deep -s - "$B/ぱずぎり挂机.app"
# App 放在「应用程序」里（用户移过去了）；编译后直接替换那里的版本
DEST="/Applications/ぱずぎり挂机.app"
rm -rf "$DEST"; ditto "$B/ぱずぎり挂机.app" "$DEST"
echo done
