#!/bin/bash
# SQLite 数据库定时备份。
#
# 为什么必须有：数据库此前零备份，只有人工临时 cp 的一份。用户、声纹档案、
# 项目与脚本全在这一个文件里，误删或磁盘故障即不可恢复——这是全项目唯一
# 「出事无法挽回」的风险点。
#
# 用 sqlite3 .backup 而非 cp：开了 WAL 后直接 cp 主库文件可能得到不一致的
# 快照（WAL 里的事务还没合并进主库）。.backup 走官方在线备份 API。
#
# 部署（root）：
#   chmod +x /www/phoenix/backend/deploy/backup_db.sh
#   (crontab -l 2>/dev/null; echo "30 4 * * * /www/phoenix/backend/deploy/backup_db.sh") | crontab -
set -euo pipefail

DB=/www/phoenix/backend/data/phoenix.db
DEST=/www/phoenix/backups
KEEP_DAYS=14

mkdir -p "$DEST"
STAMP=$(date +%Y%m%d_%H%M%S)
OUT="$DEST/phoenix_${STAMP}.db"

sqlite3 "$DB" ".backup '$OUT'"
gzip -f "$OUT"

# 校验压缩包完整，否则备份等于没有
if ! gzip -t "$OUT.gz" 2>/dev/null; then
    echo "[backup] 压缩包损坏: $OUT.gz" >&2
    exit 1
fi

# 滚动清理，避免备份自己把磁盘撑满
find "$DEST" -name 'phoenix_*.db.gz' -mtime +$KEEP_DAYS -delete

echo "[backup] ok $OUT.gz ($(du -h "$OUT.gz" | cut -f1)), 保留 ${KEEP_DAYS} 天"
