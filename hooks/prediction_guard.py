#!/usr/bin/env python3
"""Fail-closed decision for whether a tool call may modify a prediction section.

The host behavior is not verified here: this module does not know whether a
non-zero exit code actually cancels the tool, or whether the host invokes the
hook for every tool name. Callers must treat "allow" as "this input was proven
not to change a prediction section", and everything else as deny.

CHEAT_BYPASS_IMMUTABILITY is intentionally ignored. There is no bypass.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PREDICTION_HEADING = re.compile(r"^## (预测|Prediction)([^A-Za-z]|$)")
PREDICTIONS_SEGMENT = re.compile(r"(^|[\\/\"'\s])predictions([\\/\"'\s]|$)")

READONLY_TOOLS = {
    "Read",
    "Grep",
    "Glob",
    "LS",
    "WebFetch",
    "WebSearch",
    "TodoRead",
    "TodoWrite",
    "ListMcpResources",
    "ReadMcpResource",
    "ToolSearch",
    "AskUserQuestion",
    "EnterPlanMode",
    "ExitPlanMode",
    "TaskOutput",
    "TaskStop",
    "TaskCreate",
    "TaskUpdate",
    "TaskList",
    "TaskGet",
}

EDIT_TOOLS = {"Edit", "StrReplace", "search_replace", "MultiEdit"}
WRITE_TOOLS = {"Write"}
DELETE_TOOLS = {"Delete"}
SHELL_TOOLS = {"Bash", "Shell"}
NOTEBOOK_TOOLS = {"NotebookEdit"}
PATCH_TOOLS = {"ApplyPatch"}
SCAN_TOOLS = {"Task", "Skill"}

READONLY_PROGRAMS = {
    "cat",
    "head",
    "tail",
    "less",
    "more",
    "grep",
    "egrep",
    "fgrep",
    "rg",
    "wc",
    "diff",
    "cmp",
    "stat",
    "file",
    "ls",
    "pwd",
    "jq",
    "nl",
    "cut",
    "tr",
    "sort",
    "uniq",
    "date",
    "echo",
    "printf",
    "true",
    "false",
    "which",
    "command",
    "type",
    "basename",
    "dirname",
    "realpath",
    "readlink",
    "git",
}
GIT_READONLY = {"status", "diff", "log", "show", "blame", "rev-parse", "rev-list"}
MUTATING_PROGRAMS = {
    "rm",
    "mv",
    "cp",
    "tee",
    "dd",
    "truncate",
    "install",
    "ln",
    "sed",
    "perl",
    "python",
    "python3",
    "ruby",
    "node",
    "bash",
    "sh",
    "zsh",
}
INLINE_CODE_PROGRAMS = {"python", "python3", "perl", "ruby", "node", "bash", "sh", "zsh"}


@dataclass(frozen=True)
class Decision:
    allow: bool
    reason: str


def decide(payload: object, cwd: Path | None = None) -> Decision:
    """Return allow only when the call is proven not to change a prediction section."""
    if not isinstance(payload, dict):
        return Decision(False, "hook input is not a JSON object")
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name.strip():
        return Decision(False, "missing tool_name")
    base_cwd = _cwd(payload, cwd)
    if base_cwd is None:
        return Decision(False, "cannot resolve cwd")

    if tool_name in READONLY_TOOLS:
        return Decision(True, "read-only tool")

    tool_input = payload.get("tool_input")
    if tool_name in EDIT_TOOLS or tool_name in WRITE_TOOLS or tool_name in DELETE_TOOLS or tool_name in NOTEBOOK_TOOLS or tool_name in SHELL_TOOLS or tool_name in PATCH_TOOLS:
        if not isinstance(tool_input, dict):
            return Decision(False, "missing or non-object tool_input")

    if tool_name in EDIT_TOOLS:
        return _decide_edit(tool_input, base_cwd)
    if tool_name in WRITE_TOOLS:
        return _decide_write(tool_input, base_cwd)
    if tool_name in DELETE_TOOLS:
        return _decide_delete(tool_input, base_cwd)
    if tool_name in NOTEBOOK_TOOLS:
        return _decide_notebook(tool_input, base_cwd)
    if tool_name in SHELL_TOOLS:
        command = tool_input.get("command")
        if not isinstance(command, str):
            return Decision(False, "shell command missing")
        return judge_shell(command, base_cwd)
    if tool_name in PATCH_TOOLS:
        return _decide_patch(tool_input, base_cwd)
    if tool_name in SCAN_TOOLS or tool_name.startswith("mcp__"):
        return _decide_scanned(payload, base_cwd)

    return _decide_unknown(payload, base_cwd)


def judge_shell(command: str, cwd: Path) -> Decision:
    if not isinstance(command, str) or not command.strip():
        return Decision(False, "empty shell command")
    try:
        scan = _scan_shell(command)
    except _ParseError as exc:
        return Decision(False, f"unparseable shell command: {exc}")
    if scan.hard_obfuscation:
        return Decision(False, "obfuscated shell command")

    for target in scan.redirects:
        if not _is_concrete_path(target):
            return Decision(False, "redirect target cannot be resolved")
        resolved = resolve_path(target, cwd)
        lexical = lexical_path(target, cwd)
        if resolved is None or lexical is None:
            return Decision(False, "redirect target cannot be normalized")
        if under_predictions(lexical) or under_predictions(resolved):
            return Decision(False, "redirect into predictions/")

    protected = _command_mentions_protected_path(scan, cwd)
    if protected:
        if scan.command_subst:
            return Decision(False, "command substitution while naming predictions/")
        if not _segments_readonly(scan.segments):
            return Decision(False, "shell command may modify a predictions path")
        return Decision(True, "read-only inspection of predictions/")

    if scan.command_subst and scan.redirects:
        return Decision(False, "command substitution combined with redirection")

    inline = _inline_code(scan.segments)
    if inline is not None:
        return Decision(False, inline)

    unresolved = _mutating_unresolved(scan.segments)
    if unresolved is not None:
        return Decision(False, unresolved)
    return Decision(True, "shell command does not target predictions/")


def prediction_spans(text: str) -> list[tuple[int, int]]:
    """Character spans of every prediction section. Does not stop at the first other H2."""
    lines: list[tuple[int, int, str]] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        lines.append((pos, pos + len(line), line))
        pos += len(line)

    spans: list[tuple[int, int]] = []
    idx = 0
    while idx < len(lines):
        content = lines[idx][2].rstrip("\r\n")
        if PREDICTION_HEADING.match(content):
            start = lines[idx][0]
            end = lines[idx][1]
            nxt = idx + 1
            while nxt < len(lines):
                nxt_content = lines[nxt][2].rstrip("\r\n")
                if nxt_content.startswith("## ") and not PREDICTION_HEADING.match(nxt_content):
                    break
                end = lines[nxt][1]
                nxt += 1
            spans.append((start, end))
            idx = nxt
            continue
        idx += 1
    return spans


def edit_touches_prediction(text: str, old_string: str) -> str | None:
    """Return a deny reason, or None if every match sits outside all prediction spans.

    An empty span list denies: a predictions file with no recognized heading is
    not treated as safe. Any overlap, including a duplicate match inside a
    prediction section, denies. A missing match denies because the host's
    fallback is unknown.
    """
    if old_string is None or old_string == "":
        return "empty old_string"
    spans = prediction_spans(text)
    if not spans:
        return "no prediction heading; refusing instead of assuming the edit is safe"
    found = False
    start = 0
    while True:
        at = text.find(old_string, start)
        if at < 0:
            break
        found = True
        end = at + len(old_string)
        for span_start, span_end in spans:
            if at < span_end and end > span_start:
                return "edit overlaps a prediction section"
        start = at + 1
    if not found:
        return "old_string not found in file; cannot verify the edit"
    return None


def under_predictions(path: Path) -> bool:
    return "predictions" in path.parts[:-1]


def lexical_path(raw: str, cwd: Path) -> Path | None:
    if not isinstance(raw, str) or raw == "" or "\x00" in raw or "\n" in raw or "\r" in raw:
        return None
    expanded = os.path.expanduser(raw)
    path = Path(expanded)
    if not path.is_absolute():
        path = cwd / path
    return Path(os.path.normpath(str(path)))


def resolve_path(raw: str, cwd: Path) -> Path | None:
    lexical = lexical_path(raw, cwd)
    if lexical is None:
        return None
    try:
        return lexical.resolve(strict=False)
    except (OSError, RuntimeError):
        return None


def is_protected_path(raw: str, cwd: Path) -> bool | None:
    """True/False when the path can be judged, None when it cannot."""
    lexical = lexical_path(raw, cwd)
    if lexical is None:
        return None
    resolved = resolve_path(raw, cwd)
    if resolved is None:
        return None
    return under_predictions(lexical) or under_predictions(resolved)


def main(argv: list[str] | None = None) -> int:
    del argv
    raw = sys.stdin.read()
    if raw.strip() == "":
        print("BLOCKED: empty hook input; refusing because the target cannot be judged", file=sys.stderr)
        return 1
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"BLOCKED: unparseable hook input ({exc}); refusing", file=sys.stderr)
        return 1
    decision = decide(payload)
    if decision.allow:
        return 0
    print(f"BLOCKED: {decision.reason}", file=sys.stderr)
    print(
        "This hook does not make predictions tamper-proof. "
        "Whether the host actually cancels the tool call on exit code 1 has not been verified.",
        file=sys.stderr,
    )
    return 1


def _cwd(payload: dict, override: Path | None) -> Path | None:
    if override is not None:
        try:
            return override.resolve(strict=False)
        except (OSError, RuntimeError):
            return None
    raw = payload.get("cwd")
    if isinstance(raw, str) and raw.strip():
        try:
            return Path(raw).expanduser().resolve(strict=False)
        except (OSError, RuntimeError):
            return None
    try:
        return Path.cwd().resolve(strict=False)
    except (OSError, RuntimeError):
        return None


def _decide_edit(tool_input: dict, cwd: Path) -> Decision:
    paths = _path_fields(tool_input)
    if not paths:
        return Decision(False, "edit is missing a file path")
    edits = _edit_pairs(tool_input)
    if not edits:
        return Decision(False, "edit is missing old_string")
    for raw_path in paths:
        protected = is_protected_path(raw_path, cwd)
        if protected is None:
            return Decision(False, "edit path cannot be normalized")
        if not protected:
            continue
        path = resolve_path(raw_path, cwd)
        if path is None or path.is_symlink() or not path.is_file():
            return Decision(False, "prediction path is not a regular file; refusing")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            return Decision(False, f"cannot read prediction file to verify the edit: {exc}")
        for old_string, _new in edits:
            if not isinstance(old_string, str):
                return Decision(False, "old_string is not a string")
            reason = edit_touches_prediction(text, old_string)
            if reason:
                return Decision(False, reason)
    return Decision(True, "edit stays outside prediction sections")


def _decide_write(tool_input: dict, cwd: Path) -> Decision:
    paths = _path_fields(tool_input)
    if not paths:
        return Decision(False, "write is missing a file path")
    for raw_path in paths:
        protected = is_protected_path(raw_path, cwd)
        if protected is None:
            return Decision(False, "write path cannot be normalized")
        if not protected:
            continue
        path = resolve_path(raw_path, cwd)
        if path is None:
            return Decision(False, "write path cannot be normalized")
        if path.exists() or path.is_symlink():
            return Decision(False, "refusing to overwrite an existing prediction file")
    return Decision(True, "new file or path outside predictions/")


def _decide_delete(tool_input: dict, cwd: Path) -> Decision:
    paths = _path_fields(tool_input)
    if not paths:
        return Decision(False, "delete is missing a file path")
    for raw_path in paths:
        protected = is_protected_path(raw_path, cwd)
        if protected is None:
            return Decision(False, "delete path cannot be normalized")
        if protected:
            return Decision(False, "refusing to delete a path under predictions/")
    return Decision(True, "delete target is outside predictions/")


def _decide_notebook(tool_input: dict, cwd: Path) -> Decision:
    paths = _path_fields(tool_input)
    if not paths:
        return Decision(False, "notebook edit is missing a path")
    for raw_path in paths:
        protected = is_protected_path(raw_path, cwd)
        if protected is None:
            return Decision(False, "notebook path cannot be normalized")
        if protected:
            return Decision(False, "refusing notebook edit under predictions/")
    return Decision(True, "notebook path is outside predictions/")


def _decide_patch(tool_input: dict, cwd: Path) -> Decision:
    blob = json.dumps(tool_input, ensure_ascii=False)
    if "predictions" not in blob and "predictions/" not in blob:
        # Still deny if a concrete path inside the patch resolves under predictions.
        for text in _walk_strings(tool_input):
            for token in re.findall(r"[^\s\"']+", text):
                judged = is_protected_path(token.strip(","), cwd)
                if judged:
                    return Decision(False, "patch names a path under predictions/")
        return Decision(True, "patch does not name predictions/")
    return Decision(False, "refusing a patch that names predictions/; section safety cannot be proven")


def _decide_scanned(payload: dict, cwd: Path) -> Decision:
    for text in _walk_strings(payload):
        if PREDICTIONS_SEGMENT.search(text):
            return Decision(False, "payload names predictions/; cannot prove the tool will not modify it")
        for token in re.findall(r"[^\s\"']+", text):
            judged = is_protected_path(token, cwd)
            if judged:
                return Decision(False, "payload names a path under predictions/")
    return Decision(True, "payload does not name predictions/")


def _decide_unknown(payload: dict, cwd: Path) -> Decision:
    # Unknown tools are allowed only when nothing in the payload points at predictions/.
    # A tool that writes a prediction file without naming it is outside what this hook can see.
    return _decide_scanned(payload, cwd)


def _path_fields(tool_input: dict) -> list[str]:
    found: list[str] = []
    for key in ("file_path", "path", "notebook_path", "target_file"):
        value = tool_input.get(key)
        if isinstance(value, str):
            found.append(value)
    return found


def _edit_pairs(tool_input: dict) -> list[tuple[object, object]]:
    pairs: list[tuple[object, object]] = []
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for item in edits:
            if isinstance(item, dict):
                pairs.append((item.get("old_string", item.get("old_str")), item.get("new_string")))
            else:
                pairs.append((None, None))
        return pairs
    if "old_string" in tool_input or "old_str" in tool_input:
        pairs.append((tool_input.get("old_string", tool_input.get("old_str")), tool_input.get("new_string")))
    return pairs


def _walk_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
        for key in value:
            if isinstance(key, str):
                yield key
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


class _ParseError(Exception):
    pass


@dataclass
class _Scan:
    segments: list[list[str]]
    redirects: list[str]
    command_subst: bool
    hard_obfuscation: bool


def _scan_shell(command: str) -> _Scan:
    words: list[str] = []
    redirects: list[str] = []
    segments: list[list[str]] = [[]]
    command_subst = False
    hard_obfuscation = False
    buf: list[str] = []
    quote: str | None = None
    i = 0
    length = len(command)

    def flush(into_redirect: bool = False) -> None:
        nonlocal buf
        if not buf:
            return
        text = "".join(buf)
        buf = []
        if into_redirect:
            redirects.append(text)
        else:
            segments[-1].append(text)
            words.append(text)

    while i < length:
        ch = command[i]
        if quote == "'":
            if ch == "'":
                quote = None
            else:
                buf.append(ch)
            i += 1
            continue
        if quote == '"':
            if ch == "\\":
                if i + 1 >= length:
                    raise _ParseError("trailing backslash")
                buf.append(command[i + 1])
                i += 2
                continue
            if ch == '"':
                quote = None
                i += 1
                continue
            if ch == "`" or (ch == "$" and i + 1 < length and command[i + 1] == "("):
                command_subst = True
            if ch == "$" and i + 1 < length and command[i + 1] == "'":
                hard_obfuscation = True
            buf.append(ch)
            i += 1
            continue

        if ch == "\\":
            if i + 1 >= length:
                raise _ParseError("trailing backslash")
            nxt = command[i + 1]
            if nxt == "x" and i + 3 < length and re.match(r"[0-9a-fA-F]{2}", command[i + 2 : i + 4]):
                hard_obfuscation = True
            buf.append(nxt)
            i += 2
            continue
        if ch == "'":
            quote = "'"
            i += 1
            continue
        if ch == '"':
            quote = '"'
            i += 1
            continue
        if ch == "$" and i + 1 < length and command[i + 1] == "'":
            hard_obfuscation = True
            raise _ParseError("ANSI-C quote")
        if ch == "`" or (ch == "$" and i + 1 < length and command[i + 1] == "("):
            command_subst = True
            buf.append(ch)
            i += 1
            continue
        if ch == "|" and i + 1 < length and command[i + 1] == "|":
            flush()
            i += 2
            continue
        if ch == "&" and i + 1 < length and command[i + 1] == "&":
            flush()
            i += 2
            continue
        if ch == "|":
            flush()
            segments.append([])
            i += 1
            continue
        if ch == ";":
            flush()
            segments.append([])
            i += 1
            continue
        if ch == ">":
            # File descriptor duplication such as 2>&1 is not a path write.
            if i + 1 < length and command[i + 1] == "&":
                flush()
                i += 2
                while i < length and command[i].isdigit():
                    i += 1
                continue
            flush()
            if i + 1 < length and command[i + 1] == ">":
                i += 2
            else:
                i += 1
            while i < length and command[i] in " \t":
                i += 1
            target, i = _read_redirect_target(command, i)
            redirects.append(target)
            continue
        if ch in " \t\n":
            flush()
            i += 1
            continue
        buf.append(ch)
        i += 1

    if quote is not None:
        raise _ParseError("unbalanced quote")
    flush()
    if re.search(r"\beval\b", command) or re.search(r"\bbase64\b", command):
        # eval/base64 are only hard obfuscation when they appear as words, not inside single quotes.
        for segment in segments:
            for word in segment:
                if word in {"eval", "base64"}:
                    hard_obfuscation = True
    return _Scan(segments=segments, redirects=redirects, command_subst=command_subst, hard_obfuscation=hard_obfuscation)


def _read_redirect_target(command: str, i: int) -> tuple[str, int]:
    if i >= len(command):
        raise _ParseError("redirect without target")
    buf: list[str] = []
    quote: str | None = None
    while i < len(command):
        ch = command[i]
        if quote == "'":
            if ch == "'":
                quote = None
            else:
                buf.append(ch)
            i += 1
            continue
        if quote == '"':
            if ch == '"':
                quote = None
            else:
                buf.append(ch)
            i += 1
            continue
        if ch == "'":
            quote = "'"
            i += 1
            continue
        if ch == '"':
            quote = '"'
            i += 1
            continue
        if ch in " \t\n;|&":
            break
        buf.append(ch)
        i += 1
    if quote is not None:
        raise _ParseError("unbalanced quote in redirect")
    if not buf:
        raise _ParseError("empty redirect target")
    return "".join(buf), i


def _is_concrete_path(target: str) -> bool:
    if target == "" or any(ch in target for ch in "$`*?[]{}"):
        return False
    return True


def _command_mentions_protected_path(scan: _Scan, cwd: Path) -> bool:
    for segment in scan.segments:
        for word in segment:
            if PREDICTIONS_SEGMENT.search(word) or "/predictions/" in word or word.endswith("/predictions") or word == "predictions":
                return True
            if "/" in word or word.startswith("."):
                judged = is_protected_path(word, cwd)
                if judged:
                    return True
    return False


def _segments_readonly(segments: list[list[str]]) -> bool:
    saw = False
    for segment in segments:
        words = _strip_env(segment)
        if not words:
            continue
        saw = True
        prog = os.path.basename(words[0])
        if prog not in READONLY_PROGRAMS:
            return False
        if prog == "git":
            if len(words) < 2 or words[1] not in GIT_READONLY:
                return False
    return saw


def _strip_env(words: list[str]) -> list[str]:
    idx = 0
    while idx < len(words) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[idx]):
        idx += 1
    return words[idx:]


def _inline_code(segments: list[list[str]]) -> str | None:
    for segment in segments:
        words = _strip_env(segment)
        if not words:
            continue
        prog = os.path.basename(words[0])
        if prog in INLINE_CODE_PROGRAMS and any(word in {"-c", "-e", "-lc"} for word in words[1:]):
            return "inline interpreter code cannot be proven safe"
    return None


def _mutating_unresolved(segments: list[list[str]]) -> str | None:
    for segment in segments:
        words = _strip_env(segment)
        if not words:
            continue
        prog = os.path.basename(words[0])
        if prog not in MUTATING_PROGRAMS:
            continue
        for word in words[1:]:
            if word.startswith("-") and prog not in {"python", "python3", "perl", "ruby", "node"}:
                continue
            if any(ch in word for ch in "$`*?[]{}"):
                return "mutating command has an unresolved path operand"
    return None


if __name__ == "__main__":
    sys.exit(main())
