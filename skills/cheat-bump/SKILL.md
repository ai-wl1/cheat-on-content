---
name: cheat-bump
description: 在连续三次同方向的第 3 天复盘之后，把改评分写成建议交给用户。默认不把校准数据发给外部模型。用户同意后才改 rubric。触发词："升级 rubric"/"bump rubric"/"更新公式"。
argument-hint: --propose "<...>" | --bucket-only [--scheme ratio|absolute|percentile]
allowed-tools: Bash(*), Read, Write, Edit, Glob, Grep, Skill, Task, mcp__llm-chat__chat
---

# /cheat-bump — Rubric / Bucket 升级

两种模式：

| 模式 | 触发 | 做什么 | 验证强度 |
|---|---|---|---|
| **完整 rubric bump** | 连续三次同方向之后，用户要求讨论 | 先写建议；用户同意才改公式 | 本地核对。外部审核默认关闭 |
| **bucket-only 重校** | `--bucket-only` | 只重新派生 bucket 边界 | 数据自动派生，无审核 |

完整 rubric bump 严格遵守 [shared-references/bump-validation-protocol.md](../../shared-references/bump-validation-protocol.md) 的 5 步。bucket-only 走轻量路径——见下方 Phase B。

## Overview

```
入口：用户触发 /cheat-bump
  ↓
[Phase A0: 检测调用模式]
  ↓
  ├─ --bucket-only  →  [Phase B: 轻量 bucket 重校]
  └─ --propose      →  [Phase 0~6: 完整 rubric bump]
```

## Phase A0: 调用模式分流（先做）

读用户参数：
- 含 `--bucket-only` → 走 **Phase B**（轻量重校）
- 含 `--propose "<...>"` → 走 **Phase 0~8**（完整 rubric bump）
- 都没有 → 询问用户："你想做什么？1) 调 rubric 公式 / 加减维度 → --propose；2) 只重新派生 bucket 边界 → --bucket-only"

如果用户说"我觉得 ER 太低了想调"→ 是 `--propose` 路径。
如果用户说"我账号长大了，bucket 不准了"→ 是 `--bucket-only` 路径。
**两条路径不能混调**——一次操作只做一种事。

---

## 完整 rubric bump 流程

```
[用户：升级 rubric --propose "ER×1.5→2.0，砍 NA，加 MS"]
  ↓
[Phase 0: 前置门槛检查]
  ↓
[Phase 1: 写出新公式完整方程]
  ↓
[Phase 2: 校准池全量重打分]
  ↓
[Phase 3: 计算排序一致性]
  ↓
[Phase 4: 跨模型独立审核（强制）]
  ↓
[Phase 5: 落地 + cleanup pass]
  ↓
[Phase 6: 更新所有校准样本的 prediction 文件底部追加 Re-scored 行]
```

## Constants

- **READINESS_HEURISTIC** —
  - 未满连续三次同一方向的有效复盘：不提议改规则
  - 满了也只输出建议。用户明确同意之后才改 `rubric_notes.md`
  - 一次很大的偏差不够。不要用单条极端样本提前提议
- **THRESHOLD = 0.8** — 新排序与实绩排序一致性阈值（4/5）。这条**写死**——bump 验证的统计刚性
- **CROSS_MODEL_AUDIT = false** — 默认不调用外部模型。某一次要外发时，必须当次得到用户明确确认，且只发送下面 Phase 4 规定的脱敏字段
- **REQUIRE_CONFIRM = true** — 落地前要求用户明确"yes, bump"

## Inputs

| 必填 | 来源 |
|---|---|
| `--propose` 文本 | 用户参数；缺失则询问 |
| `rubric_notes.md` | 用户项目根 |
| `predictions/*.md` 全量 | 校准池数据 |
| `.cheat-state.json` | 状态 |

## Workflow

本 fork 里，改评分规则只能先写成给用户的建议。最近三次计入的发布后第 3 天复盘必须是同一方向（三次都偏高，或三次都偏低）。浏览为「不可用」、提前复盘、没有中枢的样本不计入。未满三次，就不要提议改规则，也不要修改 `rubric_notes.md`。下面关于「可以更早提议」的旧说法不再使用。

### Phase 0: 前置门槛检查

按 [bump-validation-protocol.md](../../shared-references/bump-validation-protocol.md) 的"何时禁止"段，逐项检查：

| 检查 | 失败处理 |
|---|---|
| 校准池总样本数 vs 观察强度 | **Claude 判断**——按 READINESS_HEURISTIC：默认 ≥5 样本但允许特例（强反例 / 强模因）。如不满足默认，Claude 必须**显式说明**为什么仍然提议 bump（"虽然只 N=3 样本，但 X 这条出现 composite Y vs 实绩 Z，这是 W 倍偏差"），让用户审视 |
| 上次 bump 距今的新校准数 vs 观察成熟度 | **Claude 判断**——默认建议 ≥3 篇新样本，但如果连续 3 篇都强证据指向同一方向 → 不必再等 |
| `in_progress_session == null` | 拒绝："你有 in-progress 预测未完成。先走完那条流程或清掉 state" |
| 触发条件成立（系统性偏差 / 跨样本新观察 / 新维度证据足） | 警告但不阻塞——询问用户为什么现在 bump |

通过 → 进入 Phase 1。

### Phase 1: 写出新公式完整方程

**不能只接受用户的简短描述**。把它展开为完整方程：

```
当前：v2  composite = (ER×1.5 + SR×1.5 + HP×1.5 + QL + NA + AB + SAT) / 8.5 × 2.0
提议：v2.1  composite = (ER×2.0 + HP×1.5 + MS×1.5 + QL + SR + TS + SAT) / 9.0 × 2.0

变化总结：
- ER ×1.5 → ×2.0（升）
- SR ×1.5 → ×1.0（降）
- 新增 MS ×1.5（Memetic Shareability）
- 新增 TS ×1.0（Topic Shareability）
- 删除 NA（与 HP 重叠）
- 删除 AB（被 TS 替代）
- 归一化常数 8.5 → 9.0
- 公式总维度数：7 → 7（净变化 0）
```

如果用户的提议含糊（如"ER 权重提一点"）→ 询问具体数值，**禁止自己猜**。

### Phase 2: 校准池全量重打分（**强制走 blind sub-agent**）

Glob `predictions/*.md` 中所有有完整复盘段的文件 → 校准池。

**bump 是工具最高风险动作——所有重打必须走 [cheat-score-blind](../cheat-score-blind/SKILL.md) sub-agent**。inline 重打 = 主 Claude 已经看过实绩，rank 一致性变成 overfit 而非真信号。

#### 强制约束

- **不接受 self-scored fallback**——`/cheat-predict` 有 `--skip-blind` flag，但 `/cheat-bump` **没有**。如果 Task tool 不可用 → **abort bump**，向用户报告"先解决 Task tool 再 bump"
- **不接受"我只重算 composite 不重打 dim"** —— 即使新公式只调权重不加维度，每条 prediction 的所有 dim 都要由 sub-agent 重新审 script。理由：旧 dim 分本身可能是污染的；权重变了不能保证旧 dim 还成立

#### 对每篇 prediction：

1. 解析 prediction 文件拿到对应 `scripts/<id>.md` 路径（从 `Script Path` header 字段）
2. 校验 script 文件存在 + hash 跟 header `Script Hash` 一致；不一致 → 警告（script 改过了）但仍 spawn sub-agent
3. **通过 Task tool spawn cheat-score-blind sub-agent**：
   ```
   Spawn cheat-score-blind sub-agent.

   Input:
     script_path: <prediction header 的 Script Path>
     rubric_notes_path: rubric_notes.md
     sidecar_path: .cheat-cache/bump-rescores/<prediction-id>.json

   Task: 按 rubric_notes 当前公式（已是新版 vN+1）给 script 打分。
   返回严格 JSON。写 sidecar 文件用于 bump 主流程批量读取。

   不要读 state file / predictions/ / videos/ 任何其他文件。
   不要询问用户 —— 你没有用户。
   不要读这份 prediction 文件本身 —— 你只看 script + rubric。
   ```
4. 等 sub-agent 完成 → 读 sidecar JSON → 主流程用新公式算 composite
5. 写"重打表"到 `.cheat-cache/bump-rescores.json`（汇总）。**每条 entry 标 `blind: true`** —— bump phase 5 cleanup 时把这个字段连同新分数写到 prediction 文件的 `Re-scored under v<N+1>` 行

#### 还污染没污染的诚实标注

即使走 sub-agent，**仍有两类残余 contamination 要在 bump report 里诚实标注**：

| 类型 | 来源 | 标注字段 |
|---|---|---|
| 模型 prior contamination | sub-agent 仍是 Claude，RLHF 共享 | `model_prior_warning: true`（默认 true，不可关） |
| 用户自己 rubric design bias | rubric_notes.md 是用户写的，自然 fit 自己内容 | `rubric_self_designed: true`（默认 true，不可关） |

这两条提示用户 channel C（跨模型 audit）的不可省。bump 报告末尾必印："上面的 rank 一致性是 channel A 内的一致性。**最终决策必须等 channel C audit 通过**。"

#### 失败模式

| 症状 | 处理 |
|---|---|
| 某条 prediction 的 script 文件不见了 | sub-agent skip 该条，主流程汇总报告"N 条因 script 缺失被排除"。如剩余有效池 < MIN_SAMPLES → abort bump |
| sub-agent 返回 `refusal != null` | 重发 Task 最多 3 次；仍败 → 该条标 `rescore_failed: true` 排除出校准池 |
| Task tool 整个不可用 | abort bump，提示用户"Task tool 是 bump 的硬依赖。如真的离线环境，跑 `/cheat-bump --bucket-only` 走轻量分支" |
| sub-agent 输出含 contamination_signal | 标 `suspicious: true` 但不排除——bump report 末尾列这些可疑条目让用户审 |

### Phase 3: 计算排序一致性

```
每个样本：
  new_composite_rank: 用新公式排序的 rank
  actual_plays_rank: 用实际播放排序的 rank
  delta: |new_rank - actual_rank|

输出对照表：
| 样本 | composite (v2) | composite (v2.1) | rank (new) | actual | rank (actual) | delta |
|---|---|---|---|---|---|---|
| 仓鼠 | 9.41 | 9.55 | 1 | 124.8w | 1 | 0 |
| 停止期待 | 8.24 | 9.11 | 2 | 71.1w | 2 | 0 |
| 老板废话 | 7.65 | 8.11 | 4 | 39.6w | 3 | 1 |
| 求职悖论 | 8.47 | 7.56 | 5 | 16.8w | 4 | 1 |
| 谁问你了 | 8.24 | 7.00 | 6 | 11.7w | 5 | 1 |

排序一致性：4/5 在 |delta| ≤ 1
Pairwise no-regression：旧公式做对的所有 pair 在新公式下未颠倒 ✓
```

判定：
- 排序一致性 < THRESHOLD（默认 0.8） → **本地拒绝**，转 Phase 4 之前明确报告失败
- pairwise 出现回归 → **本地拒绝**

`THRESHOLD` 写死在协议里——不允许临时调低（那本身是另一个需要 bump 的元决策）。

### Phase 4: 外部审核（默认关闭）

默认**不**调用 `mcp__llm-chat__chat`，也**不**把校准池发出去。state 里旧的 `CROSS_MODEL_AUDIT=true` 不够，每一次都要重新问。

只依赖本地判定时：在 state 标 `last_bump_self_audited: true`，然后进入 Phase 5 的用户确认。不要提示用户“去配置外部模型以便把数据发出去”。

只有用户在**这一次**对话里明确回复 `yes, send desensitized audit` 时，才可以调用外部模型。调用前把将要发送的文本原样给用户看。用户没说这句，就停止，不要自动改口发送。

允许发送的只有这些字段：

- 旧公式和新公式的算式
- 样本条数
- 排序一致的条数、pairwise 回归的条数
- 表：`sample_1` 这种不透明编号、旧 composite、新 composite、新公式名次、实绩名次

禁止发送：标题、稿件、链接、账号、评论、原始播放/点赞/回复/转发数字、Phase 2 或 Phase 3 的完整 JSON。

判定逻辑（仅在用户已确认发送并且调用成功时）：
- 本地 PASS + 外部 PASS → 进入 Phase 5
- 本地 PASS + 外部 REJECT → **视为 REJECT**
- 本地 REJECT → 已在 Phase 3 终止
- 外部调用失败 → 停止这次 bump 的外发部分，改回本地判定，并告诉用户没有数据被确认送达。不要为了完成审核而改发更全的数据。

### Phase 5: 落地 + cleanup pass

通过审核后，**REQUIRE_CONFIRM=true** → 询问用户："新公式 PASS 本地与外部审核。最后确认：执行 bump 落地？这会修改 rubric_notes.md + rubric-memo.md 并删除若干已被吸收的观察。回答 'yes, bump' 才执行。"

用户确认后：

#### 5a. 更新 `rubric_notes.md`（**只放通用语言，不含视频名 / 实绩**）

- 顶部 metadata 更新：
  - `**当前版本**: vN+1`
  - `**Last bumped at**: <ISO 8601>`
  - `**Upgrade memos**: 见 [rubric-memo.md](rubric-memo.md)`（指针，不复制 Memo 内容）
- 版本速查表加一行（只含版本号 + 公式签名，**不含**证据样本）
- 更新"当前评分维度"段（删 NA / AB，加 MS / TS）
- **派生证据段** 如新维度需要锚点解释 → **用通用语言**：
  - ✅ 允许：「派生证据：高抽象密度样本 → CC=1 → 低 reach」
  - ❌ 禁止：「派生证据：「停止期待」CC=1 → 实绩 13.7w」（视频名 + 实绩 数字）
  - 命中违禁 pattern → 把该段抽到 rubric-memo.md 的"派生证据"子段，原位用通用语言替代

#### 5b. 写 Memo 到 `rubric-memo.md`（**append 模式，不覆盖历史**）

按 [bump-validation-protocol.md](../../shared-references/bump-validation-protocol.md) Step 5 + [templates/rubric-memo.template.md](../../templates/rubric-memo.template.md) 格式 append 一段 Memo 到文件末尾：

- 触发观察（含真实观察 ID）
- 证据数据（**校准池重打表 + 排序对照，含真实视频名 + 实绩**）
- 派生证据（**含真实样本名 + 实绩**）
- 诊断
- 新公式
- 跨模型审核结论引用（含模型名 + 判定 + 理由摘录）
- 已知局限

**绝不**覆盖 rubric-memo.md 已有内容——bump memo 按时间顺序累积。

#### 5c. cleanup pass（按 [observation-lifecycle.md](../../shared-references/observation-lifecycle.md) 的"cleanup pass 强制时机"）

在 `rubric_notes.md` 内执行（**不**动 rubric-memo.md）：

- 已被吸收为新维度的观察 → 删（如观察 E 被吸收为 MS → 删观察 E）
- 被新数据推翻的观察 → 删
- 仍未解决的观察 → 迁移到新版本"待验证假设"段
- 已被验证的"规律"→ 移到"规律沉淀区"

#### 5d. 整理 + 自检

- 重新读 `rubric_notes.md` 全文，确保读者能在 60 秒内理解当下规则——超出 600 行触发额外清算
- **自检 leak guard**：对 `rubric_notes.md` 跑 `grep -E '\\d+\\s*[wWmMkK万]|播放|实绩|实际'` → 如有命中 → **abort bump + 回滚**，提示用户"rubric_notes.md 写入了违禁内容（实绩 / 播放数）"。这些内容应在 rubric-memo.md，不在 rubric_notes.md

### Phase 6: 校准样本批量更新

对每个校准样本的 prediction 文件，**底部追加**（不动预测段、不动复盘段）：

```markdown

---
**Re-scored under v2.1 on 2026-05-04**: composite=8.24 → 9.11 (blind: true)
（rubric bump 时全量重算，由 cheat-score-blind sub-agent 独立打分；详见 rubric-memo.md 的 v2 → v2.1 升级 Memo）
```

`blind: true` 字段**必填**——告诉未来读这条记录的人"这是 channel B 隔离打分，不是主 Claude 自评"。如果某条 prediction 在 Phase 2 因 sub-agent 失败被排除 → 不会有 Re-scored 行（保持原样）。

用 Edit 工具，匹配每个文件的最末尾。

### Phase 7: 更新 state file

```json
{
  "rubric_version": "v2.1",
  "last_bump_at": "<ISO timestamp>",
  "last_bump_self_audited": false,
  "consecutive_directional_errors": [],
  "calibration_samples_at_last_bump": <current value>
}
```

清空 `consecutive_directional_errors`——新 rubric 重新计数。

### Phase 8: 控制台报告

```
✅ Rubric 已升级 v2 → v2.1

变化：
- ER ×1.5 → ×2.0
- SR ×1.5 → ×1.0
- 新增 MS / TS
- 删除 NA / AB

校准池重打：5/5 通过排序检查（4/5 一致 + 0 pairwise 回归）
跨模型审核：✅ PASS
Cleanup pass：删除观察 D 和 E（已吸收为 QL 重定义和 MS 维度）

下一篇预测起按 v2.1 公式打分。
所有历史预测文件已追加 Re-scored 标记。
```

---

## Phase B：bucket-only 重校（轻量分支）

`/cheat-bump --bucket-only [--scheme ratio|absolute|percentile]`

**与完整 bump 的本质区别**：bucket 边界不是规则的一部分，是数据派生量。重新派生它**不需要跨模型审核**——派生算法是确定性的，没有"判断"成分。

### B1: 选择算法（按可用样本数自动派生，**state 不存 scheme**）

| 算法 | 适用 | 边界派生方式 |
|---|---|---|
| `ratio`（默认 N=1-4） | 小样本 | 上一篇 / 最近 3 篇中位数 × {0.3 / 1 / 3 / 10 / 30} |
| `absolute`（默认 N=5-9）| 中等样本 | 校准池中位数 × {0.3 / 1 / 3 / 10 / 30}，固定边界 |
| `percentile`（默认 N≥10）| 大样本 | 校准池实绩 percentile {30 / 60 / 85 / 95 / 100} |

`--scheme` 参数允许用户**显式覆盖默认**：
- `--scheme ratio` 强制用 ratio（即使 N≥5）
- `--scheme absolute` 强制用 absolute
- `--scheme percentile` 强制用 percentile（要求 N≥3，否则报错）

未指定 `--scheme` → 按上表自动派生。

> 旧设计有 `bucket_scheme` state 字段——v1.1 删了。所有 skill 实时按 calibration_samples 派生算法，不需要持久化"当前用哪个"。这避免了"切换 scheme 后忘了同步"的状态不一致问题。

### B2: 派生新边界

读 `predictions/*.md` 中所有有 `actual_plays` 的样本。

**ratio 模式**：
```
baseline = median(最近 3 篇 actual_plays)
buckets = {
  "退步": (-inf, baseline * 0.3),
  "持平": (baseline * 0.3, baseline * 1),
  "命中": (baseline * 1, baseline * 3),
  "小爆": (baseline * 3, baseline * 10),
  "大爆": (baseline * 10, +inf),
}
```

**absolute 模式**：
```
baseline = median(全部校准池 actual_plays)
buckets = {
  "底部": (-inf, baseline * 0.3),
  "基础盘": (baseline * 0.3, baseline * 1),
  "命中": (baseline * 1, baseline * 3),
  "爆款": (baseline * 3, baseline * 10),
  "现象级": (baseline * 10, +inf),
}
```

**percentile 模式**：
```
sorted_plays = sorted(全部校准池 actual_plays)
buckets = {
  "底部":   ≤ p30,
  "基础盘": p30 - p60,
  "命中":   p60 - p85,
  "小爆":   p85 - p95,
  "大爆":   ≥ p95,
}
```

### B3: 报告变化 + 用户确认

```
当前 bucket scheme: ratio
proposed scheme: absolute
baseline: 4.2w 中位数（基于 5 篇校准样本）

新边界：
- 底部:   < 1.3w
- 基础盘: 1.3w - 4.2w
- 命中:   4.2w - 12.6w
- 爆款:   12.6w - 42w
- 现象级: > 42w

派生说明：
- 5 篇实绩：1.5w / 3.8w / 4.2w / 5.6w / 18w
- 中位数 4.2w，新桶按 ×{0.3, 1, 3, 10} 派生

确认应用？(yes / no)
```

### B4: 落地

用户确认后：
1. 编辑 `rubric_notes.md` 的 "Bucket 方案" 段，替换为新表
2. 更新 `.cheat-state.json` 的 `baseline_plays` 字段（bucket scheme 不持久化——下次 cheat-predict 实时派生）
3. 在 `rubric_notes.md` 的 bucket 段顶部追加一行变更记录：`v2 buckets recalibrated on YYYY-MM-DD: scheme=absolute, baseline=4.2w (基于 N=10 个样本)`
4. **不**修改任何 prediction 文件——历史预测的 bucket 标签保持原样（在该样本写入时的方案下做出的判断）

### B5: 对未来预测的影响

下一次 `/cheat-predict` 起按新 bucket 派生。历史 prediction 文件里的 bucket 标签**不重算**——bucket 是预测时的语义判断，事后改写会破坏盲度。

### Phase B 不做的事

- 不重打 composite（公式没变）
- 不重新审核观察段（rubric 没变）
- 不调跨模型审核（确定性派生无需判断）
- 不要求严格的样本数门槛（按 READINESS_HEURISTIC 由 Claude 判断；ratio 模式 N=1 就能跑）

---

## Key Rules

1. **5 步不可跳**（仅完整 rubric bump）。任何"先简化跑一下"的请求都拒绝
2. **THRESHOLD 写死**（仅完整 rubric bump）。不允许动态调整
3. **外部审核默认关闭**（仅完整 rubric bump）。没有当次的 `yes, send desensitized audit`，就不得外发
4. **cleanup pass 是 bump 的一部分**（仅完整 rubric bump）。不允许 bump 完不清理观察段
5. **REQUIRE_CONFIRM**（两种模式都要）。最后落地前必须用户明确说 "yes, bump" 或 "yes, recalibrate"
6. **bucket 重校不动历史预测**。bucket 是预测时语义，事后改写破坏盲度

## Refusals

- 「跳过校准池重打，直接换公式」 → 拒绝。原则 #2
- 「跳过 cheat-score-blind sub-agent，主 Claude 直接重打就行」 → 拒绝。bump **不接受**任何 self-scored fallback——sub-agent 不可用 → abort bump，不接受"自审"
- 「把完整校准池发给外部模型」 → 拒绝。默认不外发；确认发送时也只发 Phase 4 的脱敏字段
- 「这次 THRESHOLD 调到 3/5 让它过」 → 拒绝。改 THRESHOLD 是元层级 bump
- 「保留所有旧观察作为历史」 → 违反原则 #3
- 「先 bump，cleanup 下次再做」 → 拒绝。cleanup 是 bump 的一部分
- 「只重算 composite 不重打 dim」 → 拒绝。新权重 × 旧 dim 仍是旧污染。每个 dim 都由 sub-agent 重审 script
- 「把 Memo 全文写进 rubric_notes.md 顶部，方便我读」 → 拒绝。rubric_notes.md 是 blind sub-agent 白名单——含视频名 / 实绩 → 通过白名单泄漏。Memo 写 rubric-memo.md（白名单**外**），rubric_notes.md 只放公式 + 通用语言维度定义 + 指针
- 「派生证据段保留真实视频名，让 rubric 读起来更具体」 → 拒绝。在 rubric_notes.md 必须用通用语言（"高抽象密度样本"）；带视频名的派生证据写 rubric-memo.md

## Integration

- 上游：`/cheat-retro` 检测到 ≥3 同向偏差 → 提议跑 `/cheat-bump`
- 依赖：Task tool（spawn cheat-score-blind）。外部模型不是默认依赖
- 修改：
  - `rubric_notes.md`（结构性更新，**绝不**写真实视频名 / 实绩）
  - `rubric-memo.md`（**新**——append Memo 全文，含证据 + 派生证据）
  - 所有 `predictions/*.md`（追加 Re-scored 行，不动预测段）
  - `.cheat-state.json`
- 下游：下一篇 `/cheat-predict` 自动按新 rubric_version 打分
