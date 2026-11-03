# mpflow

把一篇 Markdown 变成公众号草稿，再发布。CLI + MCP，走官方接口，不碰浏览器、不封号。

> 状态：骨架（v0.1.0-dev）。接口已通，排版引擎和 MCP 工具是最小实现。

## 为什么

技术公众号作者的日常：本地写 Markdown → 复制到网页排版工具 → 调样式 → 粘回公众号后台 → 传封面 → 存草稿 → 群发。每一步都要离开终端，AI 写的稿子也只能靠人肉搬运。

现有工具（doocs/md、mdnice）解决的是**排版**，但都是网页编辑器。没有人把整条流水线做成 CLI，也没有人让 agent 能直接调用。

mpflow 的定位：**公众号发布的 `git push`**。

## 安装

```bash
uvx mpflow --help
# 或
pip install mpflow
```

## 用法

```bash
# 1. 配置（一次）
export MP_APPID=wx...
export MP_SECRET=...

# 2. 本地预览排版效果（不调接口）
mpflow preview post.md -o preview.html

# 3. 创建草稿（会用到官方草稿箱接口）
mpflow draft post.md --thumb cover.png

# 4. 人工确认后发布
mpflow publish <media_id>
```

MCP 模式（给 Claude Code / Codex / Cursor 用）：

```bash
mpflow serve
```

暴露的工具：`render_preview`、`create_draft`、`publish_draft`、`session_status`。

## 设计约束

1. **只走官方 API**。不模拟登录、不操控浏览器，账号安全优先。
2. **发布永远需要人工确认**。`create_draft` 可以自动，`publish` 必须显式调用，不做"一键全自动群发"。
3. **排版可替换**。渲染器是一个独立模块，主题用 CSS 字典描述，方便贡献新主题。
4. **零配置起步**。没有凭证时 `preview` 仍然可用，方便先看效果。

## 路线图

- [x] 项目骨架、CLI、微信 API 客户端
- [x] Markdown → 内联样式 HTML（最小主题）
- [x] MCP server（stdio）
- [ ] 图片自动上传并替换为 `mmbiz` 链接
- [ ] 主题系统（代码高亮、引用块、表格）
- [ ] 草稿列表 / 删除 / 更新
- [ ] 发布后数据回看（阅读数、分享数）
- [ ] GitHub Action：PR 里预览排版

## 开发

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
```
