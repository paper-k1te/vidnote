# dsh-vidnote

把 [vidnote](https://github.com/paper-k1te/vidnote) 接进 DeepSeek Harness：模型可以直接抓 B 站视频、搜视频，拿到带时间戳的 Markdown 笔记。

## 给模型的两个工具

| 工具 | 作用 |
| --- | --- |
| `vidnote_note` | 给链接 / BV 号 / av 号，返回整篇笔记（标题、UP 主、分P、字幕或转写、可选关键帧） |
| `vidnote_search` | 给关键词，返回候选视频（BV 号、标题、UP 主、时长、播放量，JSON） |

## 依赖

插件本身只有几十行 JS，真正干活的是 vidnote 命令行，二选一：

- **桌面版**：`vidnote-app-full` 里的 `vidnote-server.exe`（`--profile` 安装后可在桌面版上直接用）；
- **pip 版**：`pip install 'vidnote[vosk]'`，命令行里就有 `vidnote`。

插件按这个顺序找可执行文件：

1. 配置里的 `cliPath`
2. 环境变量 `VIDNOTE_CLI`
3. `%LOCALAPPDATA%\vidnote\vidnote.exe`
4. `%USERPROFILE%\Desktop\vidnote-app-full\vidnote-server.exe`
5. PATH 上的 `vidnote`

## 安装

```sh
# 本地目录
dsh plugin --profile desktop add ./dsh-plugin

# 或者从仓库装（pnpm 需要允许 build，见 DSH 文档）
dsh plugin --profile desktop add "git+https://github.com/paper-k1te/vidnote.git#main&path:/dsh-plugin"
```

安装后重启 DSH，在会话里就能看到 `vidnote_note` / `vidnote_search`。

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

## 开发

```sh
node --test        # 10 个用例，全部是纯逻辑，不需要装 DSH
```

`lib/run.js` 不 import 任何 DSH 的包，所以测试可以在没有 DSH 的环境里跑；`index.js` 才依赖 `@deepseek-ai/dsh-tools`。

## 已知限制

- 每次工具调用会起一个 vidnote 进程，冷启动约 1 秒（单文件 exe 要解压）；
- 转写走本机 CPU，长视频会占满一个核；
- 笔记默认写到进程的工作目录，需要固定路径时在命令里用 `--dir`（插件暂未暴露该参数）。
