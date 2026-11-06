# dsh-vidnote（适配 vid2note）

把 [vid2note](https://github.com/paper-k1te/vid2note)（0.4.0 起由 vidnote 改名，Tauri 桌面端）接进 DeepSeek Harness：模型可以直接抓 B 站视频、搜视频，界面里也能抓取、看关键帧、翻历史。

插件页显示为 **vid2note — B 站视频转 Markdown 笔记**，标题/描述来自 `locale/*.json`，图标用新版的 Tauri 图标（MIT）。

## 给模型的三个工具

工具名沿用 `vidnote_*`，避免老会话失效。

| 工具 | 作用 |
| --- | --- |
| `vidnote_note` | 给链接 / BV 号 / av 号，返回整篇笔记（标题、UP 主、分P、字幕或转写） |
| `vidnote_search` | 给关键词，返回候选视频（BV 号、标题、UP 主、时长、播放量、封面，JSON） |
| `vidnote_user` | 给昵称 / 关键词，返回候选 UP 主（UID、昵称、粉丝、投稿数、签名、空间链接，JSON） |

## 依赖

插件调用本机的 vid2note 命令行，二选一：

- **pip 版**：`pip install 'vid2note[vosk]'`，命令行里有 `vid2note`（旧名 `vidnote` 也保留）；
- **桌面版**：Tauri 应用自带的 `vid2note-server.exe`。

插件按这个顺序找可执行文件：

1. 配置里的 `cliPath`
2. 环境变量 `VID2NOTE_CLI` / `VIDNOTE_CLI`
3. 仓库里的 `.venv\Scripts\vid2note.exe`（开发时直接可用）
4. 仓库里的 `dist-exe\vid2note-server.exe`、`dist-exe\vid2note.exe`，以及旧的 `vidnote*` 构建产物
5. `%LOCALAPPDATA%\vid2note\runtime\vid2note-server.exe`、`%LOCALAPPDATA%\vid2note\vid2note.exe`
6. 桌面上的 `vidnote-app*/vidnote-server.exe`（旧版）
7. PATH 上的 `vid2note`

需要读登录后才可见的字幕时，设置环境变量 `VIDNOTE_COOKIE`（值为 B 站的 SESSDATA），插件会把环境原样传给命令行。

## 安装

```sh
# 本地目录
dsh plugin --profile desktop add ./dsh-plugin

# 或者从仓库装（pnpm 需要允许 build，见 DSH 文档）
dsh plugin --profile desktop add "git+https://github.com/paper-k1te/vid2note.git#main&path:/dsh-plugin"
```

安装后重启 DSH，会话标题行会多出一个「vid2note」视图（就在「对话 / 轨迹」旁边）。

## 界面

用 DSH 自己的 slot 和主题变量重写，布局对齐 0.4.0 的新界面：

- 左侧导航：抓取视频 / 搜索 / 登录 B 站 / 下载 / 历史 / 提示；
- 抓取：链接、分P、关键帧、输出目录（可用「选择」）、解析方案；带阶段 + 百分比进度；
- 右侧三种视图：**预览 / 关键帧 / 源文**，上方是元数据头（封面、标题、UP 主、BV 号、时长、播放量）；
- 关键帧画廊：来自后端返回的 `frames`，点击在新标签页打开原图；
- 历史：最近 24 条记在浏览器 localStorage，点一下重新载入预览，可单条删除或清空；
- 深浅色跟随 DSH 主题，中英文跟随 DSH 语言，强调色保留 vid2note 的橙色；
- 状态放在模块级 store：切到「对话」再切回来不丢，抓取任务在后台继续轮询。

数据走同源代理，不重写后端：

| 路由 | 作用 |
| --- | --- |
| `/vidnote/app/api/*` | 前缀代理到 vid2note 的 `serve-ui` `/api/*`：search、fetch、job、frame、deps、pick-folder、reveal… |
| `POST /vidnote/parse` | 把 Markdown 解析成块（标题/表格/引用/列表/关键帧图片） |
| `POST /vidnote/window` | 打开 vid2note 自己的窗口：优先 Tauri 桌面端，找不到再退回 `gui --app` |

服务按需拉起，最近 5 分钟内用过就一直替它 ping，之后让它自己退出；下次再冷启动（约 3–5 秒）。默认把笔记和关键帧写到 `%LOCALAPPDATA%\vid2note\notes`（旧版是 `vidnote`），输出目录可在界面里改。

## 配置

默认设置即可用：插件自己找命令行，超时 3 分钟，不需要写配置。

只有需要固定路径或给长视频转写留更多时间时，才在 `cordis.patch.yml` 里覆盖：

```yaml
- insert:
    - id: vidnote
      name: dsh-vidnote
      config:
        cliPath: 'C:\Tools\vid2note\vid2note.exe'
        timeoutMs: 600000
```

- `cliPath`：（可选）vid2note 可执行文件路径；
- `timeoutMs`：（可选）单次调用超时，默认 180000（3 分钟）。

## 开发

```sh
node --test        # 36 个用例，纯逻辑（请求都传 fake fetch），不需要装 DSH
```

`lib/run.js`、`lib/bili.js`、`lib/api.js`、`lib/markdown.js`、`lib/proxy.js`、`lib/ui.js`、`lib/window.js` 都不 import 任何 DSH 的包；`index.js` 也不 import `@deepseek-ai/*`——宿主是从 profile 目录 import 插件的，链接进来的包解析不到安装目录里的 `@deepseek-ai/dsh-tools`，所以工具参数直接用 JSON Schema 声明。

## 排错

**`vid2note 无法解压运行环境：单文件 exe 需要可写的临时目录`**

PyInstaller 单文件 exe 启动时会解压到 `%TEMP%`。`TEMP` 不可写，或 exe 所在目录带**低完整性标签**时解压会失败。把 exe 移到普通目录，或执行：

```powershell
icacls <目录> /setintegritylevel Medium /t /c
```

**`找不到 vid2note 命令行`**

按「依赖」里的顺序显式指定：配置 `cliPath`、设置 `VID2NOTE_CLI`，或把 `vid2note` 加进 PATH。

**界面里搜索/抓取报 `HTTP 404` 或 `HTTP 405`**

客户端代码热更新了、宿主进程还是旧插件。重启 DSH 即可。

## 已知限制

- 每次工具调用会起一个 vid2note 进程，冷启动约 1 秒；界面服务第一次打开约 3–5 秒；
- 转写走本机 CPU，长视频会占满一个核；
- 界面状态和历史上限 24 条，存在**当前浏览器**里：刷新或换设备会重置，不同步；
- 界面抓取会把笔记和关键帧写进输出目录（默认 `%LOCALAPPDATA%\vid2note\notes`）；
- 「打开原界面」优先起 Tauri 桌面端；没有桌面端时退回 Edge 应用窗口，那个不跟随 DSH 主题。
