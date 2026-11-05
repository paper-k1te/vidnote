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

安装后重启 DSH，会话标题行会多出一个「B站笔记」视图（就在「对话 / 轨迹」旁边）。

## 界面

界面是**用 DSH 自己的 slot 和主题变量重写的**，不是 iframe，功能对齐原来的窗口：

- 注册为会话的第三个视图（`conversation.view`），标签「B站笔记」，和「对话」「轨迹」并列；
- 布局照着自己的窗口来：左侧导航（抓取视频 / 搜索 / 登录 B 站 / 下载）、顶栏、左边表单右边预览；
- 「抓取视频」：链接、分P、关键帧、输出目录（可用「选择」弹系统文件夹选择器）、解析方案；带**阶段 + 百分比**进度条，完成后显示告警、可切源文、复制、下载 `.md`、打开文件 / 打开文件夹；关键帧图片直接内嵌在预览里；
- 「搜索」：视频 / 作者切换，点视频把编号填回抓取页；
- 「登录 B 站」：SESSDATA/Cookie，只用于当次抓取；
- 「下载」：HuggingFace 官方 / hf-mirror 渠道，whisper 依赖状态与一键安装（带进度）；
- 深浅色跟随 DSH 主题，中英文跟随 DSH 语言，强调色保留 vidnote 的橙色；
- **状态不会因为切标签页丢失**：表单、进度、结果放在模块级 store 里，切去「对话」再切回来还在；抓取任务在后台继续轮询，回来就能看到结果。

这些能力不是重写的，而是把 vidnote 自己的 `serve-ui` 接口代理了过来：

| 路由 | 作用 |
| --- | --- |
| `/vidnote/app/api/*` | 前缀代理到 `vidnote serve-ui` 的 `/api/*`：search、fetch、job、frame、deps、pick-folder、reveal… |
| `POST /vidnote/parse` | 把 Markdown 解析成块（标题/表格/引用/列表/关键帧图片） |
| `POST /vidnote/window` | 起 `vidnote gui --app`，打开原来的独立窗口 |

服务由插件按需拉起，最近 5 分钟内用过就一直替它 ping，之后让它自己退出；下次打开再冷启动（约 3–5 秒）。默认把笔记和关键帧写到 `%LOCALAPPDATA%\vidnote\notes`，输出目录可以在界面里改。「打开原界面」是 vidnote 自己的 Edge 应用窗口（不是浏览器标签页），独立进程，关掉就结束。

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
node --test        # 33 个用例，全部是纯逻辑（请求都传 fake fetch），不需要装 DSH
```

`lib/run.js`、`lib/bili.js`、`lib/api.js`、`lib/markdown.js`、`lib/proxy.js`、`lib/ui.js`、`lib/window.js` 都不 import 任何 DSH 的包，所以测试可以在没有 DSH 的环境里跑；`index.js` 才依赖 `@deepseek-ai/dsh-tools`。

## 排错

**`vidnote 无法解压运行环境：单文件 exe 需要可写的临时目录`**

PyInstaller 单文件 exe 启动时会把自己解压到 `%TEMP%`。如果 `TEMP` 不可写，或者 exe 所在的目录被打上了**低完整性标签**（例如整棵树被某个沙箱工具标成 Low integrity），解压会失败。把 exe 移到普通目录，或对所在目录执行：

```powershell
icacls <目录> /setintegritylevel Medium /t /c
```

**`找不到 vidnote 命令行`**

按上面「依赖」里的顺序显式指定：配置 `cliPath`、设置 `VIDNOTE_CLI`，或把 vidnote 加进 PATH。

**界面里搜索/抓取报 `HTTP 404` 或 `HTTP 405`**

客户端代码热更新了、宿主进程还是旧插件（没有 `/vidnote/app` 代理和 `/vidnote/parse` 路由）。重启 DSH 即可。

## 已知限制

- 每次工具调用会起一个 vidnote 进程，冷启动约 1 秒（单文件 exe 要解压）；界面服务第一次打开约 3–5 秒，之后 5 分钟内复用；
- 转写走本机 CPU，长视频会占满一个核；
- 界面状态存在页面内存里：切「对话 / 轨迹」不会丢，刷新页面或重启 DSH 会重置；
- 界面抓取会把笔记和关键帧写进输出目录（默认 `%LOCALAPPDATA%\vidnote\notes`），不像工具那样只返回文本；
- 「打开原界面」是 vidnote 自己的 Edge 应用窗口，故意保持原样，不跟随 DSH 主题。
