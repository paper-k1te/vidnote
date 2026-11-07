已按建议补上后端会话令牌，版本 0.4.6：

- `serve-ui` 新增 `--token`（不传则启动时随机生成），`/api/*` 需要 `x-vidnote-token` 或 `?token=`；`/`、`/api/health`、`/api/ping` 放行。
- 首页把令牌嵌进 `<meta name="vid2note-token">`，桌面端 JS 自动带上；关键帧 `<img>` 用 `?token=`。
- 去掉所有 `Access-Control-Allow-Origin: *` 等 CORS 头，`OPTIONS` 只回 204。
- 插件为每个实例生成随机令牌，拉起 `serve-ui` 时传入，代理转发时统一注入；客户端自带的令牌会被覆盖。
- `/api/deps/install`、`/api/fetch`、`/api/reveal*` 等动作接口现在都在令牌之后。

验证：Python 104 个用例、插件 45 个用例通过；打包后的后端实测无令牌 401、带令牌 200，首页 meta 正确。

新提交：`6b70be2d1d447986bd69bc9ede5e5b22672baa71`（子目录 `dsh-plugin`，版本 0.4.6），已用 pnpm 从该提交安装并 import 验证通过。

Release: https://github.com/paper-k1te/vid2note/releases/tag/v0.4.6
