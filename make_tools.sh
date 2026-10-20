#!/bin/zsh
# 编译仓库里的 Swift 小工具（截图/点击/拖动/OCR/窗口定位等）
cd "${0:A:h}"
for f in input touch sweep key ocr win winbs cursor release; do
  swiftc -O -target arm64-apple-macos14.0 $f.swift -o $f || exit 1
done
echo done
