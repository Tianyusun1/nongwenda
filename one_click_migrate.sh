#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="shangchengwenda_repo"
DST_DIR="shangchengwendabao"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "[ERROR] 源目录不存在: $SRC_DIR"
  exit 1
fi

rm -rf "$DST_DIR"
cp -R "$SRC_DIR" "$DST_DIR"

# 更新项目名
if [[ -f "$DST_DIR/README.md" ]]; then
  sed -i 's/shangchengwenda_repo/shangchengwendabao/g' "$DST_DIR/README.md"
fi

# 清理缓存
find "$DST_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$DST_DIR" -type f -name "*.pyc" -delete

# 初始化独立 git 仓库
cd "$DST_DIR"
rm -rf .git
git init -b main >/dev/null 2>&1 || git init >/dev/null 2>&1

git add .
git commit -m "init: bootstrap shangchengwendabao" >/dev/null 2>&1 || true

cat <<EOF
✅ 迁移完成：$DST_DIR
下一步（可选推送远程）:
  cd $DST_DIR
  git remote add origin <你的仓库地址>
  git push -u origin main
EOF
