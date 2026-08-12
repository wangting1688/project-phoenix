#!/usr/bin/env bash
# Project Phoenix - SQLite 每日备份（封闭内测期未上 Postgres 时使用）
# 用法: ./backup_sqlite.sh   （建议加入 crontab: 0 4 * * * /path/backup_sqlite.sh）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="${ROOT}/phoenix.db"
DEST_DIR="${ROOT}/backups"
mkdir -p "$DEST_DIR"

DATE="$(date +%F_%H%M)"
DEST="${DEST_DIR}/phoenix_${DATE}.db"

if [ ! -f "$DB" ]; then
  echo "错误: 找不到数据库 $DB"; exit 1
fi

if command -v sqlite3 >/dev/null 2>&1; then
  # 在线热备，避免 WAL 下文件拷贝不一致
  sqlite3 "$DB" ".backup '${DEST}'"
else
  cp "$DB" "$DEST"
fi

# 保留最近 7 份
ls -1t "${DEST_DIR}"/phoenix_*.db 2>/dev/null | tail -n +8 | xargs -r rm -f
echo "备份完成: ${DEST}"
