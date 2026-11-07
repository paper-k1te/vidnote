0.4.6 已给后端加了会话令牌。serve-ui 新增 --token（不传则启动时随机生成），/api/* 需要 x-vidnote-token 或 ?token=，只有 /、/api/health、/api/ping 放行；去掉了 Access-Control-Allow-Origin: * 等 CORS 头，OPTIONS 只回 204。插件为每个实例生成随机令牌，拉起 serve-ui 时传入，代理转发时统一注入，客户端自带的令牌会被覆盖。/api/deps/install、/api/fetch、/api/reveal* 都已在令牌之后。

验证：Python 104 个用例、插件 45 个用例通过；打包后的后端无令牌返回 401、带令牌返回 200，首页 meta 正确；从新提交 6b70be2d1d447986bd69bc9ede5e5b22672baa71 用 pnpm 安装并 import 通过。

新提交 6b70be2d1d447986bd69bc9ede5e5b22672baa71（子目录 dsh-plugin，版本 0.4.6），Release: https://github.com/paper-k1te/vid2note/releases/tag/v0.4.6
