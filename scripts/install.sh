#!/bin/bash
# install.sh — atomic hive installation with full safety net.
# Usage: sudo ./install.sh <edited.hive> <live.hive>
set -euo pipefail
EDITED="$1"; LIVE="$2"
[ -f "$EDITED" ] || { echo "edited hive missing"; exit 1; }
[ -f "$LIVE" ] || { echo "live hive missing"; exit 1; }
STAMP=$(date +%Y%m%d-%H%M%S)
DIR=$(dirname "$LIVE"); BASE=$(basename "$LIVE")

# 1. pristine backup on volume
cp "$LIVE" "$DIR/$BASE.backup-$STAMP"; chmod 755 "$DIR/$BASE.backup-$STAMP"
echo "backup: $DIR/$BASE.backup-$STAMP"

# 2. quarantine logs + vendor backups so nothing can replay over the new base
for f in "$DIR/$BASE".LOG* "$DIR/$BASE.UBU"; do
  [ -f "$f" ] || continue
  case "$f" in *backup*|*quarantined*) continue;; esac
  mv "$f" "$f.quarantined-$STAMP"
  echo "quarantined: $(basename "$f")"
done

# 3. atomic replace
cp "$EDITED" "$DIR/$BASE.incoming"; chmod 755 "$DIR/$BASE.incoming"
mv "$DIR/$BASE.incoming" "$LIVE"
sync
echo "installed: $LIVE"

# 4. re-parse sanity
python3 - "$LIVE" <<'PY'
import sys, hivex
h = hivex.Hivex(sys.argv[1]); h.root()
print("post-install parse: OK")
PY

echo
echo "RECOVERY (if Windows rejects the hive):"
echo "  cp '$DIR/$BASE.backup-$STAMP' '$LIVE'"
