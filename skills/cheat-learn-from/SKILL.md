---
name: cheat-learn-from
description: 导入用户选定的 X 账号公开帖子。只收粘贴的文本和看得见的数字。样本少时只作定性参考。
argument-hint: "<handle>"
allowed-tools: Read, Write, Edit, Glob
---

# 对标账号

用户指定一个或多个 X 账号。不要抓取主页，不要登录，不要转写视频。

请用户从公开页面粘贴：

- 帖子全文
- 链接
- 看得到的浏览、点赞、回复、转发
- 书签仅在公开页面看得到时才记，否则「不可用（公开页面不可见）」

写入 `samples/<handle>/<id>.md` 和 `benchmark.md`（格式见 `templates/benchmark.template.md`）。

样本少于 5 条：在 `benchmark.md` 顶部写「只作定性参考」，不要建议改权重，预测精度说明仍是大约 ±50%。达到 5 条后可以描述反复出现的写法，仍然要等用户同意才改 `rubric_notes.md`，并且还要满足连续三次同方向偏差那条规则。

`benchmark_status` 在至少有 1 条粘贴样本后写成 `imported`，同时记下 `benchmark_sample_count`。
