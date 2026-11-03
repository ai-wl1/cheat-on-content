# 未审查，不要使用

这个目录里的脚本**没有**做过逐行安全审计，也**不是**当前内容流程的一部分。

不要运行这里的任何脚本，不要把它们接进 `/cheat-retro`、`/cheat-learn-from` 或其他 skill。登录态目录（`.auth/`、`.auth-xhs/`、`.auth-linkedin/`、`.auth-wechat-channels/`）等同于账号凭据，不要提交，也不要交给这个目录里的程序。

包含：

- `perf-data/douyin-session/`（抖音，Playwright 登录态）
- `perf-data/xhs-explore/`（小红书，Playwright 登录态）
- `perf-data/linkedin-session/`（LinkedIn，Playwright 登录态）
- `perf-data/wechat-channels/`（微信视频号，Playwright 登录态）
- `script-extraction/whisper/`（本地 Whisper 转写）

本次只处理了已经确认的危险行为，**没有**因此把这些适配器变成可安全使用的工具：

- 抖音 `run.sh` 不再根据“较新的 `report.md`”递归删除目录。
- 小红书、LinkedIn 的 `run.sh` 不再从父目录猜一份报告并覆盖目标（这会选错文件）。同一处猜测也从仍留在 `adapters/` 的 B 站 `run.sh` 里去掉了。
- 视频号 `run.sh` 不再在依赖和登录检查之前删除已有 `report.md`，失败时也不再删除它。`CHEAT_PYTHON` 只接受项目 `.venv` 里的解释器，不再执行任意路径。
- 小红书归档把 `note_id` 拼进目录前，拒绝含路径字符的 id。
- Whisper 只清理 `mktemp` 创建、且位于 `/tmp` 或 `/var/tmp` 的临时目录。

仍未处理、因此更不要运行：

- 小红书 `download_image()` 按数据里的 URL 下载，没有域名白名单。未改下载逻辑。
- 这些爬虫会读取并持久化平台登录态。本次没有逐行核对它们还会写出什么。
- 视频号合同测试 `test_run_contract.sh` 会调用 `run.sh`。预期已改成“失败必须留下原报告、不得执行 `.venv` 以外的 `CHEAT_PYTHON`”，但**这个测试没有运行**。
