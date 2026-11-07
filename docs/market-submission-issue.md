### 插件地址 / Plugin link

https://github.com/paper-k1te/vid2note

插件在 `dsh-plugin/` 子目录；尚未发布 npm，按固定提交收录：

- 版本：`0.4.5`
- 提交：`b6f4c26919c01481cccc0e6a2207a9cf57f54d66`
- 子目录：`dsh-plugin`

### 简短说明 / Summary

把 B 站视频抓成带时间戳的 Markdown 笔记：会话视图栏新增「vid2note」页，模型可调用 `vidnote_note` / `vidnote_search` / `vidnote_user`，支持扫码登录、关键帧、云端或 DSH 本地 SenseVoice 转写。

和只提供命令行的插件不同，它自带完整原生视图（抓取 / 搜索 / 登录 / API 设置 / 下载 / 历史 / 提示），状态切标签页不会丢。

**构建思路**：桌面端是 Tauri 2.0（Rust 外壳 + 原生 HTML/CSS/JS 工作台），后端是 Python（httpx / Pillow / PyAV / yt-dlp）。DSH 插件是纯 ESM 的 Host + Client：Host 用 `webServer` 反向代理本机 `serve-ui`，并通过 `connection.requestRejection` 做准入；Client 用 DSH 提供的 React 注册 `conversation.view`，状态放在模块级 store（`useSyncExternalStore`）。转写可走云端 Gemini / OpenAI 兼容 Whisper，或 DSH 自带的本地 SenseVoice（`ctx.speechToText`）。

### 插件实际效果 / Plugin screenshots

抓取页：左侧表单，右侧在「预览 / 关键帧 / 源文」之间切换。

![抓取与关键帧](https://raw.githubusercontent.com/paper-k1te/vid2note/main/docs/images/preview-fetch-keyframes.png)

资料页：元数据、分P、时间戳和原始 Markdown 都能核对。

![预览与资料](https://raw.githubusercontent.com/paper-k1te/vid2note/main/docs/images/preview-fetch-source.png)

搜索视频：关键词直接搜，一键带回抓取页。

![搜索视频](https://raw.githubusercontent.com/paper-k1te/vid2note/main/docs/images/preview-search-video.png)

搜索 UP 主：显示粉丝数、投稿数和空间入口。

![搜索 UP 主](https://raw.githubusercontent.com/paper-k1te/vid2note/main/docs/images/preview-search-author.png)

### 补充信息 / Additional details

- **许可证**：MIT；仓库根目录有 `LICENSE`，插件子目录里也带了一份。
- **测试环境**：DSH 0.2.1-rc.5，Windows 11 x64；`engines.dsh` 为 `>=0.1.7-rc.1`。
- **子目录可直接安装**：包含 `package.json`、`cordis.patch.yml`、`client.js`、`lib/`、`locale/`、`icon.png`、`LICENSE` 和 `README.md`；`npm pack` 共 18 个文件，已用 pnpm 从上面的固定提交 + `path:/dsh-plugin` 安装验证通过。
- **功能**：
  - 原生会话视图，复用本机 vid2note 服务的 API（进度、关键帧、目录选择、历史）；
  - B 站官方扫码登录，自动保存登录态；
  - 关键帧按画面差异挑选，和时间戳对齐；
  - 转写可选云端 Gemini / OpenAI 兼容 Whisper，或 DSH 自带的本地 SenseVoice（无需外部 Key）；
  - 三个模型工具：抓笔记、搜视频、搜 UP 主。
- **安全**：
  - 所有 `webServer` 路由都通过 `connection.requestRejection` 做准入，拿不到 `connection` 或检查抛错时直接返回 503；
  - 代理会去掉本机后端原有的 `Access-Control-Allow-Origin: *` 等宽松 CORS 头；
  - 插件自身不写文件；笔记由本机 vid2note 服务写到用户选择的输出目录；
  - 云端转写 Key 只存在本机浏览器 localStorage，随请求发往本机服务，不写进笔记、不落盘。
- **Logo**：`dsh-plugin/icon.png`（512×512）。

### 备注（给维护者）

如果可以，希望以固定提交方式收录；后续发 npm 或新版本时会在原 Issue 回复新的版本号 / 提交 SHA。截图里的路径和个人信息已做遮挡/清理。
