# vidnote

把 B 站视频变成一篇带时间戳的 Markdown 笔记：标题、UP 主、分P、简介、字幕，
全部落在一个文件里，点时间戳直接跳到视频对应位置。

```bash
vidnote fetch "https://www.bilibili.com/video/BV1xx411c7mD"
```

```markdown
**12:34** 这里是重点
```

## 为什么做这个

YouTube 那边的转写工具已经很成熟，但 B 站的视频有几个别处没有的东西：

- **分P**：一个视频可能包含几十集，笔记得知道自己在第几集
- **字幕来源不同**：B 站的字幕是 UP 主上传或 AI 生成的，接口和 YouTube 完全不同
- **时间戳参数不同**：B 站是 `?t=秒数`，多P 还要带 `&p=`
- **中文排版**：标题、简介、标签里的中文和英文混排

现有的工具大多只做 YouTube。这个工具只做一件事：**把 B 站视频归档成可检索的笔记**。

## 安装

```bash
pip install vidnote
# 或者不安装直接跑
uvx vidnote fetch BV1xx411c7mD
```

## 用法

```bash
# 基本用法：生成到当前目录
vidnote fetch BV1xx411c7mD

# 指定输出位置
vidnote fetch "https://www.bilibili.com/video/BV1xx411c7mD/?p=2" --dir ~/Notes/videos

# 直接打印，不落盘
vidnote fetch BV1xx411c7mD --stdout

# 标一个来源项目，方便以后按项目筛选
vidnote fetch BV1xx411c7mD --source my-blog
```

输出文件名形如 `2026-11-04_标题_BV1xx411c7mD.md`。文件已存在时不会覆盖，除非加 `--force`。

### 没有字幕怎么办

B 站对字幕接口做了登录限制，未登录时大多数视频拿不到字幕。这时用本地转写：

```bash
pip install 'vidnote[whisper]'
vidnote fetch BV1xx411c7mD --whisper
```

流程是：yt-dlp 取音频 → faster-whisper 在本机转写 → 生成带时间戳的笔记。音频不会上传到任何服务器。

首次运行会下载模型：

| 模型 | 大小 | 速度 | 建议 |
| --- | --- | --- | --- |
| `tiny` | ~75MB | 最快 | 只用来验证流程 |
| `base` | ~145MB | 快 | 英文内容 |
| `small`（默认） | ~485MB | 中等 | 中文内容，准确率与速度平衡 |
| `medium` | ~1.5GB | 慢 | 对准确率要求高 |

```bash
vidnote fetch BV1xx411c7mD --whisper --model medium
```

转写结果会缓存在本地（`%LOCALAPPDATA%\vidnote` 或 `~/.cache/vidnote`），同一个视频第二次跑会直接命中缓存。加 `--no-cache` 可跳过。

### 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 1 | 输入无法解析、接口报错、网络失败 |
| 3 | 目标文件已存在且没加 `--force` |

脚本里可以据此判断，不需要解析输出。

## 输出长什么样

```markdown
---
title: 一个测试视频
platform: bilibili
bvid: BV1xx411c7mD
url: https://www.bilibili.com/video/BV1xx411c7mD
owner: 某UP
duration: 1:02:03
published: 2024-05-01
fetched: 2026-11-04
language: zh-CN
subtitle: available
tags:
- bilibili
- vidnote
---

# 一个测试视频

## 视频信息
| 项目 | 内容 |
| --- | --- |
| 链接 | https://www.bilibili.com/video/BV1xx411c7mD |
...

## 字幕

**00:00** 大家好

**12:34** 这里是重点
```

frontmatter 是标准 YAML，可以直接被 Obsidian 的 Dataview 查询。

## 给 agent 用

```bash
pip install 'vidnote[mcp]'
vidnote serve
```

MCP 客户端里会多出一个工具 `fetch_note`，传链接就返回整篇笔记。

## 设计原则

1. **只读公开接口**，不模拟登录、不绕风控。
2. **不编造内容**。没有字幕就明说没有，不生成假字幕。
3. **不覆盖用户的文件**。写了笔记可能又手工补了内容，默认拒绝覆盖。
4. **可脱离软件使用**。输出是纯 Markdown，不绑定任何笔记软件。

## 路线图

- [x] B 站单P/多P 抓取、字幕、时间戳
- [x] CLI + MCP
- [x] 无字幕视频的本地转写（`--whisper`）
- [ ] 抖音、小红书
- [ ] 按章节自动切分（读简介里的时间点）
- [ ] 批量：一个收藏夹/一个 UP 主的所有视频

## 开发

```bash
pip install -e '.[dev]'
pytest
ruff check .
```

## License

MIT
