#!/usr/bin/env bash
#
# Shared checks for install.sh and uninstall.sh.
# A destination is removable only when this installer can confirm it created
# the target: either a symlink whose resolved path is the skill source, or a
# real directory containing a marker written by cheat_write_marker.
# Unconfirmed directories are never deleted.

# shellcheck shell=bash

cheat_marker_name=".cheat-on-content-managed"

cheat_dest_is_direct_child() {
  local dst="$1"
  local skill="$2"
  local parent="$3"

  [[ -n "$dst" && -n "$skill" && -n "$parent" ]] || return 1
  [[ "$skill" =~ ^[a-z0-9-]+$ ]] || return 1
  [[ "$dst" != "/" && "$dst" != "$HOME" && "$dst" != "$parent" ]] || return 1
  # Reject anything that is not exactly <parent>/<skill>.
  [[ "$(basename -- "$dst")" == "$skill" ]] || return 1
  [[ "$(dirname -- "$dst")" == "$parent" ]] || return 1
  case "$dst" in
    *..*) return 1 ;;
  esac
  return 0
}

cheat_write_marker() {
  local dst="$1"
  local skill="$2"
  local source="$3"
  local marker="$dst/$cheat_marker_name"
  local tmp

  [[ -d "$dst" && ! -L "$dst" ]] || return 1
  [[ ! -L "$marker" ]] || return 1
  tmp="$marker.tmp.$$"
  cat > "$tmp" <<EOF
managed_by=cheat-on-content
skill=$skill
source=$source
EOF
  mv -f -- "$tmp" "$marker"
}

cheat_marker_matches() {
  local dst="$1"
  local skill="$2"
  local marker="$dst/$cheat_marker_name"

  [[ -f "$marker" && ! -L "$marker" && ! -L "$dst" ]] || return 1
  grep -q -x 'managed_by=cheat-on-content' "$marker" || return 1
  grep -q -x "skill=$skill" "$marker" || return 1
}

# Prints nothing. Returns 0 if dst was absent or a confirmed target was removed.
# Returns 1 if dst exists and is not a confirmed install (caller must not delete it).
cheat_remove_confirmed_dest() {
  local dst="$1"
  local skill="$2"
  local source_real="$3"
  local parent="$4"
  local resolved parent_real dst_real

  cheat_dest_is_direct_child "$dst" "$skill" "$parent" || return 1

  if [[ ! -e "$dst" && ! -L "$dst" ]]; then
    return 0
  fi

  parent_real="$(realpath -- "$parent")"

  if [[ -L "$dst" ]]; then
    resolved="$(realpath -- "$dst" 2>/dev/null || true)"
    if [[ -n "$resolved" && "$resolved" == "$source_real" ]]; then
      rm -- "$dst"
      return 0
    fi
    return 1
  fi

  if [[ -d "$dst" ]]; then
    cheat_marker_matches "$dst" "$skill" || return 1
    dst_real="$(realpath -- "$dst")"
    case "$dst_real" in
      "$parent_real"/*) ;;
      *) return 1 ;;
    esac
    rm -rf -- "$dst"
    return 0
  fi

  return 1
}

# Remove a .git directory that this run just copied into dst.
# Refuses when .git is a symlink or resolves outside dst.
cheat_strip_copied_git() {
  local dst="$1"
  local git_dir="$dst/.git"
  local git_real dst_real

  [[ -d "$dst" && ! -L "$dst" ]] || return 0
  [[ -e "$git_dir" || -L "$git_dir" ]] || return 0
  if [[ -L "$git_dir" ]]; then
    echo "refusing to remove symlink $git_dir" >&2
    return 1
  fi
  [[ -d "$git_dir" ]] || return 0
  git_real="$(realpath -- "$git_dir")"
  dst_real="$(realpath -- "$dst")"
  if [[ "$git_real" != "$dst_real/.git" ]]; then
    echo "refusing to remove $git_dir because it does not resolve inside the copy" >&2
    return 1
  fi
  rm -rf -- "$git_dir"
}
