#!/usr/bin/env bash
# Exercises managed_install.sh in a temp directory.
# Does not call install.sh, uninstall.sh, or any adapter.
set -euo pipefail

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# shellcheck source=managed_install.sh
source "$SCRIPT_DIR/managed_install.sh"

TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT

SOURCE="$TMP/source/cheat-init"
PARENT="$TMP/skills"
mkdir -p "$SOURCE" "$PARENT"
printf 'name: cheat-init\n' > "$SOURCE/SKILL.md"
SOURCE_REAL="$(realpath -- "$SOURCE")"

# Unconfirmed directory must survive.
mkdir -p "$PARENT/cheat-init"
printf 'user data\n' > "$PARENT/cheat-init/keep.txt"
if cheat_remove_confirmed_dest "$PARENT/cheat-init" "cheat-init" "$SOURCE_REAL" "$PARENT"; then
  echo "unconfirmed directory was removed" >&2
  exit 1
fi
[[ -f "$PARENT/cheat-init/keep.txt" ]]

# Confirmed copy may be removed.
cheat_write_marker "$PARENT/cheat-init" "cheat-init" "$SOURCE_REAL"
cheat_remove_confirmed_dest "$PARENT/cheat-init" "cheat-init" "$SOURCE_REAL" "$PARENT"
[[ ! -e "$PARENT/cheat-init" ]]

# Symlink pointing elsewhere must survive. Symlink pointing at the source may be unlinked.
mkdir -p "$TMP/other/cheat-init"
ln -s "$TMP/other/cheat-init" "$PARENT/cheat-init"
if cheat_remove_confirmed_dest "$PARENT/cheat-init" "cheat-init" "$SOURCE_REAL" "$PARENT"; then
  echo "foreign symlink was removed" >&2
  exit 1
fi
[[ -L "$PARENT/cheat-init" ]]
rm -- "$PARENT/cheat-init"

ln -s "$SOURCE" "$PARENT/cheat-init"
cheat_remove_confirmed_dest "$PARENT/cheat-init" "cheat-init" "$SOURCE_REAL" "$PARENT"
[[ ! -e "$PARENT/cheat-init" && ! -L "$PARENT/cheat-init" ]]
[[ -f "$SOURCE/SKILL.md" ]]

# A .git symlink inside a fresh copy must not be followed.
mkdir -p "$PARENT/cheat-init" "$TMP/realgit"
cheat_write_marker "$PARENT/cheat-init" "cheat-init" "$SOURCE_REAL"
ln -s "$TMP/realgit" "$PARENT/cheat-init/.git"
if cheat_strip_copied_git "$PARENT/cheat-init"; then
  echo "symlink .git was accepted" >&2
  exit 1
fi
[[ -d "$TMP/realgit" ]]

echo "managed_install_test: ok"
