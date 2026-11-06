# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.3.3] - 2026-11-06

### 新增

- **DeepSeek Harness 插件**：`dsh-plugin/` 把 vidnote 接进 DSH，模型可以直接调用 `vidnote_note`（链接 → 带时间戳的 Markdown）、`vidnote_search`（关键词 → 候选视频 JSON）和 `vidnote_user`（关键词 → 候选 UP 主 JSON）；带中英文标题、描述和图标，安装一条命令即可。
- **原生 DSH 界面**：会话视图栏里「对话 / 轨迹」旁边多一个「B站笔记」视图，布局照着原窗口（左侧导航 + 表单 + Markdown 预览）；抓取进度、关键帧、输出目录、Cookie、whisper 依赖通过代理复用 `serve-ui` 接口，功能与原窗口对齐，状态切标签页不丢；「打开原界面」拉起 vidnote 自己的独立应用窗口。
- 插件把单文件 exe 解压失败（`PYI-xxxx`）翻译成可操作的提示，不再只抛一行 bootloader 错误。

### 变更

- **桌面端统一为一个构建**：唯一的桌面发布包内置 Vosk 引擎和中文模型，第一次转写不用下载；完整版不再单独构建/发布，whisper 依赖仍按需安装。
- **DSH 插件按默认设置工作**：安装后无需配置，自动按 `cliPath` → `VIDNOTE_CLI` → 仓库构建产物 → 常见安装位置 → PATH 的顺序找命令行，默认超时 180 秒；只有需要固定路径或长视频转写时才改 `cliPath` / `timeoutMs`。

### 修复

- **插件可以从 git 直接安装**：去掉了指向私有包的 `peerDependencies`，并清掉 `package.json` 的 BOM；`pnpm` 之前会去 npm 拉 `@deepseek-ai/dsh-tools`（404），或者直接 JSON 解析失败。
- 插件代理补齐 `Content-Length`，修掉浏览器里怎么点都提示「请输入 B 站视频链接、BV 号或 av 号」的问题。

## [0.3.1] - 2026-11-05

### 新增

- **搜索作者**：搜索页支持「视频 / 作者」切换，作者结果显示昵称、粉丝数、视频数和签名，点击可直接打开 B 站空间；作者接口偶发 412 时会自动重试并退回 `all/v2` 的 `bili_user` 分组。
- **exe 图标与版本信息**：桌面版加入橙色 V 图标，并在文件属性中写入公司 `Paperkite Studio`、产品 `vidnote` 和版本号。

### 变更

- **whisper 推理引擎改为按需安装**：完整版 exe 不再内置 ctranslate2 / onnxruntime / tokenizers 等（约 66 MB），第一次在界面里选 whisper 时点「安装 whisper 依赖」单独下载；完整版从约 162 MB 降到约 101 MB。同时剔除未使用的 cryptography / OpenSSL、websockets、sqlite3，保留 yt-dlp 所需的 requests / urllib3。
- **Vosk 自动分句补标点**：利用逐词时间戳按停顿断句，并在句尾补 `。？！`，不再输出一整段无标点文本。

## [0.3.0] - 2026-11-05

### 新增

- **桌面版改为单文件 exe**：窗口外壳、Python 后端和 WebView2 库全部内置；首次启动释放到 `%LOCALAPPDATA%\vidnote\runtime`，用户目录里只保留一个 `vidnote-app.exe`。
- **可选登录 B 站**：在表单顶部填入 SESSDATA，能读取登录后才显示的字幕；Cookie 只用于当次请求，不写入笔记，也不保存。
- **“打开文件夹”按钮**：生成笔记后可在资源管理器里定位文件，目标为目录时直接打开。

### 变更

- **完整版 exe 内置 Vosk 模型**：中文模型随安装包一起分发，第一次转写不再下载 42 MB 模型；whisper 模型仍按需下载。
- **界面重排**：登录选项移到表单最上方并默认收起；“没有字幕时”改为“解析方案”，只保留方案与效果，下载渠道单独成项。
- **输出目录可选文件夹**：输出目录旁新增“选择”按钮，调用系统文件夹选择器，不用手动输入路径。
- **桌面窗口适配高 DPI**：外壳改为 PerMonitorV2，并按屏幕缩放换算窗口尺寸；150% / 200% 缩放下文字不再发虚，布局也不会被压窄。

## [0.2.4] - 2026-11-04

### 新增

- **视频信息抓得更全**：改用 `view/detail` 接口，补上标签、分区、UP 主 mid 与空间链接、播放 / 点赞 / 投币 / 收藏 / 弹幕 / 评论数据；接口降级时也会单独补标签。
- **b23.tv 短链自动展开**：链接、BV 号、av 号之外，粘贴短链（含不带 `https://` 的形式）也能识别。
- **完整版重新内置 whisper**：界面里可以重新选择 whisper tiny / base / small，模型第一次使用时才下载。
- **转写模型下载进度**：GUI 在按钮下方显示阶段和百分比；CLI 进度条覆盖「下载音频 → 下载模型 → 本地转写」三个阶段。

### 变更

- **笔记默认生成 6 张关键帧**：`--frames 6` 成为默认值，填 0 关闭；关键帧按时间插在对应字幕后面，没有字幕时单独成节。
- 关键帧失败（没有缩略图、CDN 不可达、目录不可写）不再中断笔记生成，只提示并跳过。
- 网页界面支持预览笔记里的关键帧图片（新增 `/api/frame`，只允许读取笔记所在目录的图片）。

### 修复

- 发布时间按北京时间计算，凌晨发布的视频不会再显示成前一天。

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
