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

安装后重启 DSH，会话里就能看到 `vidnote_note` / `vidnote_search` / `vidnote_user`，Web 界面右下角也会出现「B站」按钮。

## 交互窗口

插件没有重写 vidnote 的界面，而是把原来那个窗口整扇搬进来：

1. 点「B站」按钮 → 前端 `GET /vidnote/url`；
2. 宿主的这条路由会用 `vidnote serve-ui --port <空闲端口>` 拉起本地服务，轮询 `/api/health` 直到就绪；
3. 前端拿到地址后用一个 iframe 铺满弹窗，里面就是 `vidnote/ui/index.html` 原页面；
4. 关掉弹窗，页面停止 ping，服务 20 秒后自动退出，不留后台进程。再次打开会重新拉起。

要求 vidnote 支持 `serve-ui`（0.3.0 起，桌面版和 pip 版都有）。窗口和服务都只监听 `127.0.0.1`。

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
| `frames` | 导出关键帧张数，0 表示不抽 |
| `transcribe` | 留空不转写；`vosk-cn` 用 Vosk 小模型（42 MB）；`tiny`/`base`/`small` 用 whisper |

`vidnote_search` / `vidnote_user`：`keyword` 必填，`limit` 默认 10（`vidnote_user` 最多 50）。

## 开发

```sh
node --test        # 20 个用例，全部是纯逻辑（请求都传 fake fetch），不需要装 DSH
```

`lib/run.js`、`lib/bili.js`、`lib/ui.js` 都不 import 任何 DSH 的包，所以测试可以在没有 DSH 的环境里跑；`index.js` 才依赖 `@deepseek-ai/dsh-tools`。

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
- 交互窗口是 iframe 嵌的另一个本地端口，和 DSH 页面不同源；快捷键、主题跟随由 vidnote 页面自己决定，不跟 DSH 的深色模式联动。
