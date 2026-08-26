#!/usr/bin/env bash
# Archive a scene cache directory to GitHub as an orphan branch of split tar
# parts (<=90MB per file, so no LFS/Releases needed - both are unavailable in
# this environment). The orphan branch shares no history with main, so normal
# single-branch clones never download it.
#
# Usage:   scripts/archive_cache_to_git.sh [cache_dir] [branch]
# Restore: git fetch origin cache-archive-fleet-v1
#          git show <sha>:MANIFEST  (list parts)
#          git archive cache-archive-fleet-v1 | tar -x   # extracts parts/
#          cat parts/cache_fleet.tar.part-* | tar -x     # recreates cache dir
set -euo pipefail
CACHE_DIR=${1:-data/cache_fleet}
BRANCH=${2:-cache-archive-fleet-v1}
PARTS=data/cache_archive_parts
cd "$(dirname "$0")/.."

rm -rf "$PARTS" && mkdir -p "$PARTS"
NAME=$(basename "$CACHE_DIR")
echo "taring $CACHE_DIR ..."
tar -cf - "$CACHE_DIR" | split -b 90m - "$PARTS/${NAME}.tar.part-"
( cd "$PARTS" && sha256sum ${NAME}.tar.part-* > MANIFEST && du -sh . )

echo "building orphan commit ..."
export GIT_INDEX_FILE=$(mktemp)
rm -f "$GIT_INDEX_FILE"
git -C ../ rev-parse --show-toplevel >/dev/null  # sanity: inside a repo
for f in "$PARTS"/*; do
  git update-index --add --cacheinfo 100644,$(git hash-object -w "$f"),"parts/$(basename "$f")"
done
TREE=$(git write-tree)
COMMIT=$(git commit-tree "$TREE" -m "Landsat scene cache archive: $CACHE_DIR ($(date -u +%F))
Restore: cat parts/${NAME}.tar.part-* | tar -x
Reproducible alternative: re-run the fetch scripts against Planetary Computer.")
unset GIT_INDEX_FILE
echo "pushing $COMMIT -> $BRANCH ..."
git push -u origin "$COMMIT:refs/heads/$BRANCH"
echo "done: branch $BRANCH"
