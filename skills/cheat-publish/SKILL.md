---
name: cheat-publish
description: 生成 X 网页发帖链接，等人点发送后再登记公开 URL。不调用发帖 API。
argument-hint: <prediction-or-draft>
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# 发帖链接

不调用 X 的发帖 API，也不要打开网络去发帖。

## 生成链接

用本地函数，不要手写一半编码：

在 cheat-on-content 仓库里运行（内容项目目录里通常没有这份脚本）：

```bash
python3 <cheat-on-content>/tools/x_intent.py --text '<定稿全文>'
python3 <cheat-on-content>/tools/x_intent.py --text '<回复全文>' --in-reply-to '<数字帖子 id>'
```

`tools/x_intent.py` 只做字符串处理。回复必须带数字 `in_reply_to`。引用转发不使用 `in_reply_to`，引用的 URL 放在正文里。

把得到的 `https://x.com/intent/post?text=...` 给用户。说明要点击后自己按发送。在用户回来贴出公开 URL 或帖子 id 之前，不要把这篇标成已发布。

## 登记

用户贴出 `https://x.com/<user>/status/<id>` 或帖子 id 之后，写入预测文件头部（预测段之上的元数据，不要改 `## 预测` 正文）：

- `Published at`: 用户确认的日期
- `Public URL`
- `Post ID`
- `采集窗口`: 发布后第 3 天

`posts_published` 加 1。不要为了登记去抓取该 URL。
