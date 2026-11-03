# Cheat on Content — X 信息源账号

这个 fork 把闭环用在一个 AI 信息源 X 账号上：新闻简评带来源链接，或者回复、引用转发大 V 的帖子。

顺序是打分、盲预测、生成发帖链接、人自己点发送、发布后第 3 天把公开页面上的数字记下来。

不接发帖 API。不登录后台。不抓外部热点。`legacy/UNREVIEWED-DO-NOT-USE/` 里的脚本未审查，不要运行。

## 指标

发布后第 3 天，从帖子公开页面手抄：

- 浏览
- 点赞
- 回复
- 转发
- 书签可以记，但要注明公开页面是否看得见

看不到的写「不可用」，不要写成 0。页面上就是 0 才写 0。

没有对标账号时，预测精度按大约 ±50% 的工作假设写进模板。这不是实测。

前 5 篇只收集数据，不按分数决定发不发。连续三次同一方向的偏差之后，才可以把改评分写成建议，由人决定。

没有带来源链接、值得发的材料时，输出「今天没有」。不要编链接、数字或引语。

## 发帖链接

仓库里的 `tools/x_intent.py` 只在本地拼 URL，不联网：

```bash
python3 tools/x_intent.py --text '简评。来源：https://example.com/post'
python3 tools/x_intent.py --text '回复' --in-reply-to '1234567890'
```

得到 `https://x.com/intent/post?text=...`。回复会多一个 `&in_reply_to=`。打开后由人按发送。

## 预测段

写完不改。复盘只追加。`hooks/prediction-immutability.sh` 会尝试拒绝修改。下面两件事没有在这里验证：宿主是否对每次工具调用都跑这个钩子，以及退出码 1 是否会取消那次调用。所以不能说文件已经不可篡改。

## 安装

在本仓库根目录执行。安装器只替换它能确认是自己装上的技能目录；同名但没有标记的目录会留下。

```bash
bash install.sh
bash install.sh --codex
bash uninstall.sh
```

不要用 `curl | bash` 安装任何附属脚本。

初始化时在内容项目里说「初始化」。日常说法见 [SKILL.md](SKILL.md)。

## 许可

MIT。上游是 XBuilderLAB/cheat-on-content。
