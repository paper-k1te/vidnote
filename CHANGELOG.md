# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.2.3] - 2026-11-04

### 变更

- **转写换成 Vosk 小引擎**：完整版不再打包 `faster-whisper`，改为 Vosk——运行库 13 MB，中文模型 42 MB（首次使用才下载）。完整版从 101 MB 降到 74 MB，模型从 485 MB 降到 42 MB。
- 界面里可选引擎：Vosk（42 MB，快、无标点）或 whisper 的 tiny/base/small（需 `pip install 'vidnote[whisper]'`，不随桌面版分发）。
- 命令行新增 `--vosk`；`--whisper` 保留给 pip 安装的用户。

### 修复

- PyInstaller 没有收集 Vosk 的原生 `libvosk.dll`，exe 里引擎显示为不可用——在 spec 里补 `collect_dynamic_libs("vosk")`。
- 缓存目录在受限账户下不可写（`%LOCALAPPDATA%` 被拒绝）时，依次回退到 `~/.cache` 和临时目录，不再直接报错。

## [0.2.2] - 2026-11-04


### 变更

- **转写模型可选，默认不再下载 485 MB**：界面里改成三选一——`tiny` 75 MB / `base` 145 MB / `small` 485 MB，默认仍是「不转写」，只有主动选择才会下载模型。
- 界面上直接标出每个模型的下载体积和适用场景，避免默认拉一个 485 MB 的大包。

## [0.2.1] - 2026-11-04

补完 0.2.0 的桌面形态：真窗口、界面重构、转写集成。

### 新增

- **桌面应用（原生窗口）**：`scripts/build_app.ps1` 生成 `dist-app\vidnote-app.exe`——WinForms + WebView2 外壳，双击即用，没有浏览器地址栏，退出时自动关闭后端。
- **完整版构建**：`scripts/build_app.ps1 -Full` 把 `faster-whisper`、`yt-dlp` 一并打进去（约 102 MB），界面里勾选「在本机转写」即可处理没有字幕的视频。
- **界面里直接转写**：后端新增 `transcribe` 能力探测，`/api/health` 返回是否支持；轻量版会把开关置灰并说明原因。
- **界面重构**：采用 cc-switch 的设计 token（浅底灰阶 + 橙色强调色 + 13px 字号），新增侧栏导航、深浅色切换、Markdown 实时预览。
- **Windows 单文件 exe**：`scripts/build_exe.ps1` 生成 `dist-exe\vidnote.exe`（约 15 MB），包含抓取、搜索、笔记生成和缩略帧，不需要安装 Python。
- **缩略帧改用 B 站雪碧图**：`--frames` 默认只下载一张拼图再裁剪，不再下载视频、不需要 PyAV 和系统 ffmpeg。
- **`--scene`**：需要按画面变化选帧时使用，走视频解码路径，依赖 `vidnote[scene]`。
- exe 里运行 `vidnote serve` 时，会明确提示这是核心版、MCP 需要 pip 安装的完整版。

### 变更

- Pillow 改为核心依赖；原来的 `[frames]` 额外依赖组更名为 `[scene]`。

### 修复

- **Windows 中文乱码**：控制台默认代码页是 GBK，程序输出却是 UTF-8。现在启动时统一把控制台代码页和输出流设为 UTF-8。

### 体积

单文件 exe 的构成与取舍：

| 组成 | 体积 |
| --- | --- |
| 核心（Python 运行时 + httpx/typer/rich/PyYAML） | ~13.5 MB |
| Pillow（裁剪缩略帧） | +6.5 MB |
| 去掉 PIL 的 AVIF / 字体 / WebP 扩展 | −5.5 MB |
| **最终** | **15.1 MB** |

转写（faster-whisper + ctranslate2 + onnxruntime）会让体积超过 300 MB，因此不进 exe。

## [0.2.0] - 2026-11-04

### 新增

- **关键词搜索**：`vidnote search "关键词"`，列出 BV 号、标题、UP 主、时长、播放量；`--json` 可给脚本用。走公开的 `search/all/v2` 接口，不需要登录。
- **关键帧提取**：`--frames N` 会按画面变化挑选关键帧，导出 JPEG 到笔记旁边的 `<笔记名>_frames/` 目录，并在笔记里生成带时间戳的「关键帧」一节。纯本地计算，不调用 AI。
- **本地视频输入**：`--video <文件>`，跳过下载直接分析已有视频，适用于视频 CDN 不可达的网络环境。
- 新增可选依赖组 `[frames]`（PyAV + yt-dlp + Pillow）。

### 变更

- 关键帧的最小间隔改为按视频时长自动计算，短视频也能选出多张，不再固定 8 秒。

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
