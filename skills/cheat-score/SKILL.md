---
name: cheat-score
description: 按 X 短帖 rubric 给单帖、回复或引用转打发分。不写预测文件，也不决定发不发。
argument-hint: <draft-path>
allowed-tools: Read, Grep, Glob
---

# 打分

读取 `starter-rubrics/short-text-zero.md`（用户项目里则以 `rubric_notes.md` 为准）和指定草稿。只在对话里给出分数，不写 `predictions/`。

## 步骤

1. 确认类型：单帖、回复或引用转发。
2. 没有用户材料中的来源链接：不要打分。若这是在选题，输出「今天没有」。
3. 每个维度要么是 0–5，要么是「不适用」。缺失不要打成 0。
4. 综合分只除以适用维度的个数。
5. 草稿里的数字和引语必须能在用户给的材料里找到。找不到就标出来，不要补。

## 前 5 篇

`posts_published` 小于 5 时，分数后面写一句：前 5 篇只收集数据，这个分数不决定发不发。不要加「建议不要发」或「建议发」。
