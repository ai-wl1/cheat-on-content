---
name: cheat-shoot
description: 把 X 草稿登记为定稿。不拍摄，不转写视频。
argument-hint: <draft-path>
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# 定稿

用户确认这篇就是要发出去的文本之后：

1. 检查来源链接还在，而且不是新编的。
2. 把定稿抄到 `posts/<id>/post.md`。目录不存在就创建。
3. 如果定稿和 `scripts/` 里的草稿不同，用 `tools/diff_pct.py` 算差异，把百分比写进 `posts/<id>/post.md` 顶部的注释。这个工具只读本地文件。
4. 在 `.cheat-state.json` 的 buffer 里记下这篇已定稿、未发布。

不要运行 Whisper，不要创建 `videos/`。

没有来源链接就停，并说明缺链接。不要改已写的预测段。
