# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-11-04

第一个可用版本。

### 新增

- **B 站视频抓取**：支持视频链接、BV 号、av 号，自动读取标题、UP 主、时长、发布时间、简介、标签。
- **分P 支持**：多P 视频可指定 `--page`，笔记里记录当前分P，时间戳链接自动带 `?p=`。
- **字幕优先**：视频有可用字幕时直接使用，保留原始时间戳。
- **本地转写**：没有字幕时，用 `--whisper` 走 yt-dlp + faster-whisper 在本机转写，音频不上传。
- **转写缓存**：按「视频 + 分P + 模型」缓存，重复处理同一视频不再重复转写。
- **Markdown 输出**：YAML frontmatter + 视频信息表 + 可点击时间戳，适配 Obsidian 等笔记工具。
- **CLI**：`fetch` / `serve` / `version`，退出码 0/1/2/3，方便脚本判断。
- **MCP server**：`vidnote serve` 暴露 `fetch_note` 工具，供 Claude Code、Codex、Cursor 等调用。
- **`--delay`**：批量循环时在接口请求之间插入等待，降低请求频率。

### 已知限制

- 只支持 B 站，暂不支持抖音、小红书、YouTube。
- 未登录状态下大多数视频拿不到字幕，本地转写是主要路径。
- `tiny` 模型对中文效果较差，默认使用 `small`。
- Windows 上已锁定 `av<14`，因为 faster-whisper 1.2 与 PyAV 14+ 不兼容。

[0.1.0]: https://github.com/paper-k1te/vidnote/releases/tag/v0.1.0
