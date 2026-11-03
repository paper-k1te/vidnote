<p align="center">
  <img src="assets/banner.svg" alt="vidnote" width="100%">
</p>

<h1 align="center">vidnote</h1>

<p align="center">
  <b>把 B 站视频变成一篇带时间戳的 Markdown 笔记。</b><br>
  <sub>标题 · UP 主 · 分P · 简介 · 字幕，一个文件装完，点时间戳直接跳到视频对应位置。</sub>
</p>

<p align="center">
  <a href="https://github.com/paper-k1te/vidnote/actions/workflows/ci.yml"><img src="https://github.com/paper-k1te/vidnote/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-07C160" alt="MIT License">
  <img src="https://img.shields.io/badge/MCP-ready-00A1D6" alt="MCP ready">
  <img src="https://img.shields.io/badge/本地转写-无需_API_Key-8957E5" alt="Local transcription">
</p>

<p align="center">
  <a href="#-它能做什么">它能做什么</a> ·
  <a href="#-快速开始">快速开始</a> ·
  <a href="#-没有字幕怎么办">本地转写</a> ·
  <a href="#-给-agent-用">给 agent 用</a> ·
  <a href="#-常见问题">FAQ</a> ·
  <a href="#english">English</a>
</p>

---

```console
$ vidnote fetch BV1xx411c7mD --whisper
✓ 已生成 2026-11-04_标题_BV1xx411c7mD.md  （本地转写，412 条）
```

打开就是这个样子：

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
language: zh
subtitle: available
tags:
- bilibili
- vidnote
---

## 字幕

**00:00** 大家好，今天想聊一个很多人问过的问题。

**12:34** 这里是重点，我把它拆成三步。
```

## ✨ 它能做什么

- **一条命令归档**：链接、BV 号、av 号都认，自动抓标题、UP 主、时长、发布时间、简介、标签。
- **分P 不迷路**：多P 视频会记录当前在第几集，时间戳链接自动带上 `&p=`。
- **字幕优先，转写兜底**：视频有字幕就直接用；没有就在本机跑 Whisper，音频不出你的电脑。
- **时间戳可点**：`[12:34](…?t=754)`，在 Obsidian、Logseq、浏览器里都能跳转。
- **YAML frontmatter**：字段固定，能被 Dataview 之类的工具直接查询、筛选、聚合。
- **CLI + MCP 双入口**：人用命令行，agent 用 MCP 工具，同一套逻辑。

## 🚀 快速开始

```bash
pip install vidnote
```

```bash
# 链接、BV 号、av 号都行
vidnote fetch "https://www.bilibili.com/video/BV1xx411c7mD"

# 第 2 个分P
vidnote fetch "https://www.bilibili.com/video/BV1xx411c7mD/?p=2"

# 只打印，不写文件
vidnote fetch BV1xx411c7mD --stdout

# 存到笔记库，并标记来源
vidnote fetch BV1xx411c7mD --dir ~/Notes/videos --source my-blog
```

没装包也可以直接跑：

```bash
uvx vidnote fetch BV1xx411c7mD
```

### 退出码

| 码 | 含义 |
| :--: | --- |
| `0` | 成功 |
| `1` | 输入无法解析、接口报错、网络失败 |
| `2` | 缺少可选依赖（如转写所需的 whisper） |
| `3` | 目标文件已存在，且没有加 `--force` |

脚本里判断退出码即可，不需要解析输出。

## 🔊 没有字幕怎么办

B 站对字幕接口做了登录限制，**未登录时大多数视频拿不到字幕**。所以真正的主力是本地转写：

```bash
pip install 'vidnote[whisper]'
vidnote fetch BV1xx411c7mD --whisper
```

流程：`yt-dlp` 取音频 → `faster-whisper` 在本机转写 → 生成带时间戳的笔记。**音频不会上传到任何服务器。**

首次运行会下载模型：

| 模型 | 大小 | 速度 | 建议 |
| --- | ---: | --- | --- |
| `tiny` | 75 MB | 最快 | 只用来验证流程，中文质量差 |
| `base` | 145 MB | 快 | 英文内容 |
| `small`（默认） | 485 MB | 中等 | 中文内容，速度与准确率的平衡点 |
| `medium` | 1.5 GB | 慢 | 对准确率要求高 |

```bash
vidnote fetch BV1xx411c7mD --whisper --model medium
```

转写结果按 `视频 + 分P + 模型` 缓存在本地（Windows 在 `%LOCALAPPDATA%\vidnote`，其他系统在 `~/.cache/vidnote`），同一个视频第二次跑秒出。加 `--no-cache` 可跳过。

## 🤖 给 agent 用

装上 MCP 依赖后，把 vidnote 注册成一个 MCP server：

```bash
pip install 'vidnote[mcp]'
vidnote serve
```

Claude Code / Codex / Cursor 的配置：

```json
{
  "mcpServers": {
    "vidnote": {
      "command": "vidnote",
      "args": ["serve"]
    }
  }
}
```

agent 会多出一个工具 `fetch_note`：

| 参数 | 说明 |
| --- | --- |
| `target` | 链接、BV 号或 av 号 |
| `page` | 分P 序号，默认 1 |
| `include_desc` | 是否包含简介，默认 `true` |
| `transcribe` | 没有字幕时是否本地转写，默认 `false` |

## 🎯 为什么只做 B 站

YouTube 的转写生态已经很成熟，但把同一套思路搬到 B 站会撞上三件不同的事：

1. **分P 是常态**。一个系列几十集，笔记必须知道自己在第几集，链接必须带 `p`。
2. **字幕拿不到**。B 站的字幕接口对未登录请求基本返回空，不能像 YouTube 那样"读字幕"了事，必须本地转写。
3. **时间戳格式不同**。B 站是 `?t=秒数`，和 YouTube 的 `&t=754s` 不是一回事。

所以这个项目的定位不是"又一个转写工具"，而是**把 B 站特有的这层壳处理掉**。同类工具（如 [video-fetcher-to-markdown](https://github.com/JimmySadek/video-fetcher-to-markdown)）在英文平台上做得很好，但 B 站的分P、UP 主语义、中文字幕格式都需要单独适配。

## 🧭 设计原则

1. **只读公开接口**。不模拟登录、不绕风控、不批量抓取。
2. **不编造内容**。没有字幕就说没有，不会用模型编一段假字幕。
3. **不覆盖你的文件**。笔记里可能有你手写的内容，默认拒绝覆盖，必须显式 `--force`。
4. **可脱离软件使用**。输出是纯 Markdown，不绑定 Obsidian 或任何笔记软件。
5. **失败要可诊断**。每个错误都给出下一步该做什么，而不是只抛一个异常。

## ❓ 常见问题

<details>
<summary><b>会被 B 站封号吗？</b></summary>

这个工具只读取公开的视频信息和匿名可访问的接口，不登录、不发布、不改动你的账号。但**请控制请求频率**，不要拿它做批量爬取。若你要处理的视频很多，加个延迟。
</details>

<details>
<summary><b>需要 OpenAI 或其他 API Key 吗？</b></summary>

不需要。转写在本地用 `faster-whisper` 跑，不联网、不调用任何云端模型。
</details>

<details>
<summary><b>转写太慢怎么办？</b></summary>

换小模型（`--model base` 或 `tiny`），或者接受一次性的等待——转写结果会缓存，同一个视频只慢一次。长视频（1 小时以上）用 `small` 在普通笔记本上大约需要 10–20 分钟。
</details>

<details>
<summary><b>为什么笔记里没有字幕？</b></summary>

说明这个视频没有可用字幕，而你也没加 `--whisper`。工具会明确写出"没有可用字幕"，而不是留空。
</details>

<details>
<summary><b>支持抖音、小红书、YouTube 吗？</b></summary>

暂不支持，见路线图。当前只把 B 站这一条链路做扎实。
</details>

<details>
<summary><b>Windows 上有什么坑？</b></summary>

`faster-whisper` 依赖的 PyAV 在 14 之后改了接口，和部分版本不兼容。项目的 `[whisper]` 依赖已经锁定了可用版本，正常 `pip install` 不会踩到。
</details>

## 🗺 路线图

- [x] B 站单P/多P 抓取、字幕、时间戳
- [x] 无字幕视频的本地转写
- [x] CLI + MCP
- [ ] 按简介里的时间点自动生成章节
- [ ] 批量：一个收藏夹 / 一个 UP 主的所有视频
- [ ] 抖音、小红书
- [ ] 导出为 SRT / VTT

## 🛠 开发

```bash
git clone https://github.com/paper-k1te/vidnote.git
cd vidnote
pip install -e '.[dev]'

pytest          # 22 个测试
ruff check .    # 代码检查
```

CI 覆盖 Ubuntu 与 Windows，Python 3.10 / 3.12 / 3.13。

## 📄 许可证

[MIT](LICENSE)。可自由使用、修改、商用，保留版权声明即可。

---

<a id="english"></a>

## English

**vidnote** turns a Bilibili video into a timestamped Markdown note: title, uploader,
multi-part awareness, description, and a transcript — all in one portable file with
clickable timestamps.

```bash
vidnote fetch "https://www.bilibili.com/video/BV1xx411c7mD" --whisper
```

- Uses Bilibili's public web API; no login, no scraping workarounds.
- If a video has no captions (most don't without a session), transcribe locally with
  `faster-whisper` — audio never leaves your machine.
- Output is plain Markdown with YAML frontmatter, ready for Obsidian or any tool.
- Ships a CLI and an MCP server (`vidnote serve`) for coding agents.

MIT licensed.
