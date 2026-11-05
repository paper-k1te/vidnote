# dsh-vidnote

把 [vidnote](https://github.com/paper-k1te/vidnote) 接进 DeepSeek Harness：模型可以直接抓 B 站视频、搜视频，拿到带时间戳的 Markdown 笔记。

装好后「插件」页里显示为 **vidnote — B 站视频转 Markdown 笔记**（英文界面为 *vidnote — Bilibili to Markdown notes*），标题和描述来自 `locale/*.json`，图标用仓库里的 `assets/vidnote.png`（MIT）。

## 给模型的两个工具

| 工具 | 作用 |
| --- | --- |
| `vidnote_note` | 给链接 / BV 号 / av 号，返回整篇笔记（标题、UP 主、分P、字幕或转写、可选关键帧） |
| `vidnote_search` | 给关键词，返回候选视频（BV 号、标题、UP 主、时长、播放量，JSON） |
| `vidnote_user` | 给昵称 / 关键词，返回候选 UP 主（UID、昵称、粉丝、投稿数、签名、空间链接，JSON） |

窗口本身也在插件里：Web 界面右下角会多一个「B站」圆钮，点开就是原来的 vidnote 交互窗口（抓取表单、搜索、进度、关键帧预览），详见下面「交互窗口」。

## 依赖

插件本身只有几十行 JS，真正干活的是 vidnote 命令行，二选一：

- **桌面版**：`vidnote-app-full` 里的 `vidnote-server.exe`（`--profile` 安装后可在桌面版上直接用）；
- **pip 版**：`pip install 'vidnote[vosk]'`，命令行里就有 `vidnote`。

插件按这个顺序找可执行文件：

1. 配置里的 `cliPath`
2. 环境变量 `VIDNOTE_CLI`
3. 仓库里的 `dist-exe-full/vidnote-server.exe`、`dist-exe/vidnote.exe`（开发时直接可用）
4. `%LOCALAPPDATA%\vidnote\vidnote.exe`
5. 桌面上的 `vidnote-app*/vidnote-server.exe`
6. PATH 上的 `vidnote`

需要读登录后才可见的字幕时，设置环境变量 `VIDNOTE_COOKIE`（值为 B 站的 SESSDATA），插件会把环境原样传给命令行。

## 安装

```sh
# 本地目录
dsh plugin --profile desktop add ./dsh-plugin

# 或者从仓库装（pnpm 需要允许 build，见 DSH 文档）
dsh plugin --profile desktop add "git+https://github.com/paper-k1te/vidnote.git#main&path:/dsh-plugin"
```

安装后重启 DSH，会话里就能看到 `vidnote_note` / `vidnote_search` / `vidnote_user`，左侧边栏也会多一个「B站笔记」入口。

## 原生界面

界面是**用 DSH 自己的组件和主题变量重写的**，不是 iframe：

- 左侧边栏一个纸鸢图标，点开是主区域的一整页「B站笔记」；
- 「抓取视频」：链接、分P、关键帧、解析方案，生成后结果直接渲染在下方，可复制 / 下载 `.md`，抓取期间有等待计时；
- 「搜索」：视频 / UP 主切换，点视频会把链接填回抓取页；
- 深浅色跟随 DSH 主题（全部用 `--dsw-alias-*` 变量），中英文跟随 DSH 语言。

数据走三条同源接口：

| 接口 | 作用 |
| --- | --- |
| `POST /vidnote/api/fetch` | 调 `vidnote fetch --stdout`，返回 Markdown |
| `POST /vidnote/api/search` | 视频走 `search/all/v2`，UP 主走 `search/type` |
| `GET /vidnote/url` | 可选：拉起 `vidnote serve-ui`，给「打开原界面」用 |

「打开原界面」会打开原来的 vidnote 窗口（要求 vidnote 支持 `serve-ui`，0.3.0 起）。原窗口关掉后服务 20 秒自动退出，不留后台进程。所有服务都只监听 `127.0.0.1`。

## 配置

`cordis.patch.yml` 里可以覆盖默认值：

```yaml
- insert:
    - id: vidnote
      name: dsh-vidnote
      config:
        cliPath: 'C:\Tools\vidnote\vidnote.exe'
        timeoutMs: 600000
```

- `cliPath`：vidnote 可执行文件路径；
- `timeoutMs`：单次调用超时，默认 180000（3 分钟）。转写长视频要调大。

## 参数说明

`vidnote_note`：

| 参数 | 说明 |
| --- | --- |
| `target` | 必填，B 站链接 / BV 号 / av 号 |
| `page` | 分P 序号，默认 1 |
| `transcribe` | 留空不转写；`vosk-cn` 用 Vosk 小模型（42 MB）；`tiny`/`base`/`small` 用 whisper |

注意：工具走 `--stdout`，vidnote 在这个模式下会跳过关键帧（传 `--frames` 反而会让进程以 1 退出），所以关键帧只在「打开原界面」或直接用 CLI 时才有。

`vidnote_search` / `vidnote_user`：`keyword` 必填，`limit` 默认 10（`vidnote_user` 最多 50）。

## 开发

```sh
node --test        # 29 个用例，全部是纯逻辑（请求都传 fake fetch），不需要装 DSH
```

`lib/run.js`、`lib/bili.js`、`lib/api.js`、`lib/ui.js` 都不 import 任何 DSH 的包，所以测试可以在没有 DSH 的环境里跑；`index.js` 才依赖 `@deepseek-ai/dsh-tools`。

## 排错

**`vidnote 无法解压运行环境：单文件 exe 需要可写的临时目录`**

PyInstaller 单文件 exe 启动时会把自己解压到 `%TEMP%`。如果 `TEMP` 不可写，或者 exe 所在的目录被打上了**低完整性标签**（例如整棵树被某个沙箱工具标成 Low integrity），解压会失败。把 exe 移到普通目录，或对所在目录执行：

```powershell
icacls <目录> /setintegritylevel Medium /t /c
```

**`找不到 vidnote 命令行`**

按上面「依赖」里的顺序显式指定：配置 `cliPath`、设置 `VIDNOTE_CLI`，或把 vidnote 加进 PATH。

## 已知限制

- 每次工具调用会起一个 vidnote 进程，冷启动约 1 秒（单文件 exe 要解压）；
- 转写走本机 CPU，长视频会占满一个核；
- 工具带 `--stdout`，笔记只回到会话里，不写文件；要落盘就用 CLI 的 `vidnote fetch ... --dir ...`；
- 原生界面里的抓取是「一次请求等到结束」，没有逐条进度：转写长视频时只能看到等待计时，进度条仍是原窗口的；
- 「打开原界面」打开的仍是 vidnote 自己的页面（另一个本地端口），它不跟随 DSH 主题。
