---
name: cheat-init
description: 初始化 AI 信息源 X 账号项目。只建立本地目录和手动录入。不安装登录态适配器。
argument-hint: ""
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# 初始化

在用户的内容目录里建闭环所需的文件。已有文件不覆盖，除非用户明确说覆盖这一份。

## 要问的事

1. 项目目录是不是当前目录。
2. 有没有要导入的 X 对标账号。没有就写 `benchmark_status: none`。预测精度按大约 ±50% 的工作假设记录。
3. 大 V 名单放哪。默认 `big-v.md`，可以是空文件。
4. 每日摘要文件放哪。默认 `digest/`。这是另一个模块写好的本地文件，本技能不拉取。
5. 要不要把预测钩子复制到 `.cheat-hooks/`。要的话同时复制 `prediction-immutability.sh` 和 `prediction_guard.py`，并说明宿主是否拦截**未验证**。

不要询问抖音、小红书、视频号、LinkedIn 或 Whisper 的安装。那些目录是 `legacy/UNREVIEWED-DO-NOT-USE/`，不要运行。

## 要创建的文件

- `rubric_notes.md`：复制 `starter-rubrics/short-text-zero.md`
- `scripts/` `predictions/` `posts/` `samples/` `digest/`
- `big-v.md`：标题写「大 V 名单」，下面留空
- `candidates.md`：可以是空的
- `.cheat-state.json`，至少包含：

```json
{
  "schema_version": "1.4",
  "content_form": "x-short-post",
  "account_role": "ai-news-source",
  "calibration_samples": 0,
  "data_collection": "manual",
  "enabled_perf_adapters": [],
  "enabled_trend_sources": ["manual-paste"],
  "benchmark_status": "none",
  "retro_window_days": 3,
  "cross_model_audit": false,
  "posts_published": 0
}
```

`cross_model_audit: false` 只是默认。它不能代替某一次 bump 里用户当次的确认。

## 不要做

- 不运行 `install.sh` 以外的安装器；初始化本身不调用安装脚本，除非用户明确在仓库根目录要求安装技能
- 不联网抓热点
- 不登录任何平台
- 不把 `videos/` 当本流程的数据目录
