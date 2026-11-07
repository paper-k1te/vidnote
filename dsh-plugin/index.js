import { createHandlers } from './lib/api.js'
import { guarded } from './lib/admission.js'
import { searchUsers } from './lib/bili.js'
import { createProxy } from './lib/proxy.js'
import { buildArgs, resolveCli, runVidnote } from './lib/run.js'
import { createSttServer } from './lib/stt.js'
import { createUiServer } from './lib/ui.js'
import { openAppWindow } from './lib/window.js'

export const name = 'dsh-vidnote'
export const inject = ['tools', 'webServer', 'connection']

/**
 * 把 vid2note（原 vidnote）接到 DSH 里：模型可以直接抓 B 站视频、搜视频/搜 UP 主。
 *
 * 插件不 import 任何 @deepseek-ai 包：宿主插件是从 profile 目录 import 的，而
 * @deepseek-ai/* 只存在于 DSH 安装目录，从链接进来的插件里解析不到（会报
 * "Cannot find package '@deepseek-ai/dsh-tools'"）。所以参数直接用宿主认的 JSON
 * Schema 声明，工具定义就是普通对象。
 *
 * 模型看到三个工具：
 *   - vidnote_note   给链接/BV 号，返回整篇笔记
 *   - vidnote_search 给关键词，返回候选视频列表
 *   - vidnote_user   给关键词，返回候选 UP 主
 *
 * 浏览器侧是「对话 / 轨迹」旁边的第三个视图，界面走代理复用 vid2note 自己的
 * serve-ui 接口（进度、关键帧、选目录、打开文件、whisper 依赖都在那边）。
 */
export async function apply(ctx, config = {}) {
  const cliPath = resolveCli(config)
  const timeoutMs = Number(config.timeoutMs) || 180_000

  // 把 DSH 自带的本地语音识别（SenseVoice）借给后端；没有启用 voice-input
  // bundle 时端点仍然起来，但请求会返回 503 和原因。
  let stt = null
  let sttEnv = {}
  try {
    stt = createSttServer(ctx)
    await stt.ready
    sttEnv = { VID2NOTE_STT_URL: stt.url, VID2NOTE_STT_TOKEN: stt.token }
    ctx.effect(() => () => stt.stop())
  } catch {
    stt = null
    sttEnv = {}
  }

  const ui = createUiServer({
    cliPath,
    env: {
      ...process.env,
      ...sttEnv,
      ...(config.asrKey ? { VID2NOTE_ASR_KEY: String(config.asrKey) } : {}),
      ...(config.asrBase ? { VID2NOTE_ASR_BASE: String(config.asrBase) } : {}),
      ...(config.asrModel ? { VID2NOTE_ASR_MODEL: String(config.asrModel) } : {}),
      ...(config.asrProvider ? { VID2NOTE_ASR_PROVIDER: String(config.asrProvider) } : {}),
    },
  })
  ctx.effect(() => () => ui.stop())

  const api = createHandlers()
  ctx.effect(() => ctx.webServer.register({
    kind: 'exact',
    path: '/vidnote/parse',
    handler: guarded(ctx.connection, api.parse),
  }))

  // /vidnote/app/api/* → 本地 serve-ui 的 /api/*（流式代理，图片和进度都在里面）
  const proxy = createProxy(async () => {
    await ui.ensure()
    return ui.origin()
  })
  ctx.effect(() => ctx.webServer.register({
    kind: 'prefix',
    path: '/vidnote/app',
    handler: guarded(ctx.connection, proxy),
  }))

  // 「打开原界面」：优先 Tauri 桌面端，找不到再退回 `gui --app`。
  ctx.effect(() => ctx.webServer.register({
    kind: 'exact',
    path: '/vidnote/window',
    handler: guarded(ctx.connection, async (_req, res) => {
      try {
        openAppWindow({ cliPath })
        res.writeHead(200, {
          'content-type': 'application/json; charset=utf-8',
          'cache-control': 'no-store',
        })
        res.end(JSON.stringify({ ok: true }))
      } catch (error) {
        res.writeHead(502, {
          'content-type': 'application/json; charset=utf-8',
          'cache-control': 'no-store',
        })
        res.end(JSON.stringify({ error: String(error?.message ?? error) }))
      }
    }),
  }))

  const renderText = (_args, value) => [{ type: 'text', text: value }]

  ctx.tools.register({
    name: 'vidnote_note',
    description:
      '把 B 站视频抓成一篇带时间戳的 Markdown 笔记（标题、UP 主、分P、字幕或本地转写）。',
    parameters: {
      type: 'object',
      properties: {
        target: { type: 'string', description: 'B 站链接、BV 号或 av 号' },
        page: { type: 'number', description: '分P 序号，默认 1' },
        transcribe: {
          type: 'string',
          description:
            "没有字幕时用哪个引擎转写：留空=不转写；'vosk-cn'=Vosk 小模型（42 MB，推荐）；'tiny'/'base'/'small'=whisper",
        },
      },
      required: ['target'],
      additionalProperties: false,
    },
    output: { schema: { type: 'string' }, render: renderText },
    async execute(args, exec) {
      const target = String(args?.target ?? '').trim()
      if (!target) throw new Error('请先填入 B 站链接或 BV 号。')
      const argv = buildArgs('fetch', args)
      return runVidnote(argv, { cliPath, timeoutMs, signal: exec?.signal })
    },
  })

  ctx.tools.register({
    name: 'vidnote_search',
    description: '按关键词搜索 B 站视频，返回 BV 号、标题、UP 主、时长和播放量（JSON 文本）。',
    parameters: {
      type: 'object',
      properties: {
        keyword: { type: 'string', description: '搜索关键词' },
        limit: { type: 'number', description: '返回条数，默认 10' },
      },
      required: ['keyword'],
      additionalProperties: false,
    },
    output: { schema: { type: 'string' }, render: renderText },
    async execute(args, exec) {
      const keyword = String(args?.keyword ?? '').trim()
      if (!keyword) throw new Error('搜索关键词不能为空。')
      const argv = buildArgs('search', args)
      return runVidnote(argv, { cliPath, timeoutMs, signal: exec?.signal })
    },
  })

  ctx.tools.register({
    name: 'vidnote_user',
    description:
      '按关键词搜索 B 站 UP 主（作者），返回 UID、昵称、粉丝数、投稿数、签名和空间链接（JSON 文本）。',
    parameters: {
      type: 'object',
      properties: {
        keyword: { type: 'string', description: '要查的 UP 主昵称或关键词' },
        limit: { type: 'number', description: '返回条数，默认 10，最多 50' },
      },
      required: ['keyword'],
      additionalProperties: false,
    },
    output: { schema: { type: 'string' }, render: renderText },
    async execute(args, exec) {
      const keyword = String(args?.keyword ?? '').trim()
      if (!keyword) throw new Error('搜索关键词不能为空。')
      const limit = Math.min(Math.max(Number(args.limit) || 10, 1), 50)
      const users = await searchUsers(keyword, { limit, signal: exec?.signal })
      return JSON.stringify(users, null, 2)
    },
  })
}
