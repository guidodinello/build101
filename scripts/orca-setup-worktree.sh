#!/usr/bin/env bash
# Bootstraps a new worktree of build101: copies the gitignored .env files from
# the main checkout and installs backend (uv) and frontend (npm) dependencies.
#
# Meant for Orca's per-repo "Worktree Hooks -> Setup Script"
# (Settings -> Git & Source Control), pointing at the main checkout's copy so
# it also works on branches that predate this file:
#   bash /path/to/build101/scripts/orca-setup-worktree.sh
# Orca runs it with $ORCA_WORKTREE_PATH set to the new worktree's path; without
# it, the current directory is used. Safe to re-run: never overwrites an
# existing .env file in the worktree.
set -euo pipefail

WORKTREE_DIR="${ORCA_WORKTREE_PATH:-$(pwd)}"
cd "$WORKTREE_DIR"

# The first entry of `git worktree list` is always the main checkout, which is
# where the real (gitignored) .env files live.
MAIN_DIR="$(git worktree list --porcelain | awk '/^worktree /{print substr($0, 10); exit}')"

if [ "$MAIN_DIR" = "$WORKTREE_DIR" ]; then
  echo "==> This is the main checkout, nothing to copy"
else
  # Every .env / .env.* except the committed .env.example templates.
  while IFS= read -r -d '' src; do
    rel="${src#"$MAIN_DIR"/}"
    dest="$WORKTREE_DIR/$rel"
    if [ -f "$dest" ]; then
      echo "==> $rel already exists, leaving it alone"
    else
      mkdir -p "$(dirname "$dest")"
      cp "$src" "$dest"
      echo "==> Copied $rel from the main checkout"
    fi
  done < <(find "$MAIN_DIR" \
    \( -name node_modules -o -name .venv -o -name .next -o -name .git \) -prune -o \
    -type f -name '.env*' ! -name '*.example' -print0)
fi

for dir in backend frontend; do
  if [ -f "$dir/.env.example" ] && [ ! -f "$dir/.env" ] && [ ! -f "$dir/.env.local" ]; then
    echo "==> WARNING: $dir has no .env (none in the main checkout either); copy $dir/.env.example and fill it in" >&2
  fi
done

echo "==> Installing backend dependencies (uv sync)"
(cd backend && uv sync)

echo "==> Installing frontend dependencies (npm ci)"
(cd frontend && npm ci)

echo "==> Bootstrap done. Run: (cd backend && uv run uvicorn app.main:app --reload) / (cd frontend && npm run dev)"
