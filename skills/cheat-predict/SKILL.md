---
name: cheat-predict
description: 为 X 草稿写盲预测。写完不改预测段。无对标时写明精度大约 ±50%。
argument-hint: <draft-path>
allowed-tools: Bash(*), Read, Write, Grep, Glob
---

# 盲预测

看到这条帖子发布后的浏览、点赞、回复、转发之前，把预测写入新文件。已有预测文件时不要覆盖。要重做就新建 `*_redo.md`。

## 拒绝

- 对话里已经有这条帖子的发布后数字
- 草稿没有来源链接
- 用户要求按实绩反推预测

## 写入

路径：`predictions/<草稿同一日期>_<id>_<short>.md`

按 `templates/prediction.template.md`。中枢是浏览次数的整数，不要用「万」或 `w`。

无对标账号（`benchmark_status` 不是 `imported`，或对标样本少于 5 且只能定性）时，文件里写：无对标账号时，预测精度大约 ±50%。这是工作假设，不是实测。

桶名只用 `<50`、`50-500`、`500-5000`、`5000-50000`、`>50000`。不要附上没有依据的先验概率。

## 前 5 篇

预测照写。不要根据分数或中枢告诉用户发还是不发。
