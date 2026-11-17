#!/bin/bash
# 掃描指定的檔案／資料夾，結果寫到 output/（可用環境變數 OUT_DIR 覆寫）。
# 用法：./scan_files.sh 檔案1 檔案2 ...；不給參數時掃描 inbox/ 資料夾。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="${OUT_DIR:-$HERE/output}"

PY="${PYTHON:-$(command -v python3 || true)}"
if [ -z "$PY" ]; then
    echo "找不到 python3，請先安裝 Python 3。" >&2
    exit 1
fi

# 沒有傳入任何檔案時，掃描 inbox/ 資料夾
if [ "$#" -eq 0 ]; then
    mkdir -p "$HERE/inbox"
    set -- "$HERE/inbox"
fi

cd "$HERE"
exec "$PY" vocab_scanner.py "$@" --out-dir "$OUT_DIR"
