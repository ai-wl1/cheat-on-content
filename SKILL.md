---
name: cheat-on-content
description: AI 信息源 X 账号的发帖前打分、盲预测、发布后第 3 天复盘。内容是 AI 新闻简评加来源链接，以及对大 V 帖子的回复或引用转发评论。触发词："初始化"/"打分"/"预测"/"定稿"/"发帖链接"/"复盘"/"选题"/"对标"/"状态"。首次先初始化。
argument-hint: "[draft-path]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill
---

# X 帖闭环

给一个 AI 信息源账号用：打分 → 盲预测 → 人点开发帖链接 → 发布后第 3 天用公开页面复盘。

不接发帖 API，不登录后台，不运行 `legacy/UNREVIEWED-DO-NOT-USE/` 里的脚本。

## 三条规则

1. **盲预测**。预测写在看到这条帖子的发布后数据之前。写完不改 `## 预测` 段，复盘只追加。钩子会尝试拒绝修改，但宿主是否拦截**未验证**，不能说成不可篡改。规范：[shared-references/blind-prediction-protocol.md](shared-references/blind-prediction-protocol.md)。
2. **改规则要慢**。只有连续三次有效的第 3 天复盘是同一方向（都偏高或都偏低）才可以提议改评分。提议交给用户，用户不接受就不改。
3. **不编造**。每条草稿都要有用户材料里的来源链接。没有值得发的，只输出「今天没有」。

## 路由

| 用户说 | 读取 |
|---|---|
| 初始化 | `skills/cheat-init/SKILL.md` |
| 找对标 / 导入某 X 账号 | `skills/cheat-learn-from/SKILL.md` |
| 选题 / 今天发什么 | `skills/cheat-seed/SKILL.md` |
| 打分 | `skills/cheat-score/SKILL.md` |
| 预测 | `skills/cheat-predict/SKILL.md` |
| 定稿 | `skills/cheat-shoot/SKILL.md` |
| 发帖链接 / 已发布 | `skills/cheat-publish/SKILL.md` |
| 复盘 | `skills/cheat-retro/SKILL.md` |
| 推荐下一条 | `skills/cheat-recommend/SKILL.md` |
| 热点 / 今日材料 | `skills/cheat-trends/SKILL.md` |
| 状态 | `skills/cheat-status/SKILL.md` |
| 改评分规则 | `skills/cheat-bump/SKILL.md` |

没有 `.cheat-state.json` 时，先初始化。

## 必须拒绝

- 先看浏览或点赞再补写预测
- 修改已写好的 `## 预测` 段。重做就新建 `_redo.md`
- 用分数决定前 5 篇发不发
- 没有来源链接还写草稿，或编造数字、引语、链接
- 抓取热点、登录平台、运行 legacy 目录里的脚本
- 调用发帖 API。只生成 `https://x.com/intent/post?text=` 链接，由人点发送
- 未满连续三次同方向偏差就改评分规则，或用户没同意就改
- 把「不可用」写成 0
- 把完整校准数据发给外部模型。默认不外发

## 目录

```
scripts/                 草稿。每份含来源链接
predictions/             预测。预测段不改
posts/                   发布记录。report.md 由用户粘贴的公开数字写成
samples/                 对标账号的公开帖子文本
candidates.md            选题。可以是空的
big-v.md                 用户给的大 V 名单
digest/                  另一个模块留下的每日摘要文件，只当本地输入
rubric_notes.md          从 starter-rubrics/short-text-zero.md 复制
benchmark.md             可没有
.cheat-state.json
.cheat-hooks/            prediction-immutability.sh 与 prediction_guard.py
```

不使用 `videos/`。不创建 `.auth*`。

## 指标

浏览、点赞、回复、转发。书签可以记，但要写公开页面是否看得见。采集窗口是发布后第 3 天。缺失写「不可用」。

## 前 5 篇

这 5 篇的分数和预测只是记录。不要据此建议发或不发。第 6 篇起可以对照先前的偏差说话，仍然由人决定发不发。
