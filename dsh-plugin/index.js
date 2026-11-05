import { defineTool } from '@deepseek-ai/dsh-tools'
import { createHandlers } from './lib/api.js'
import { searchUsers } from './lib/bili.js'
import { createProxy } from './lib/proxy.js'
import { buildArgs, resolveCli, runVidnote } from './lib/run.js'
import { createUiServer } from './lib/ui.js'
import { openAppWindow } from './lib/window.js'

export const name = 'dsh-vidnote'
export const inject = ['tools', 'webServer']

/**
 * 把 vidnote 接到 DSH 里：模型可以直接抓 B 站视频、搜视频/搜 UP 主，拿到带时间戳的 Markdown。
 *
 * 模型不直接跑命令行，只看到三个工具：
 *   - vidnote_note   给链接/BV 号，返回整篇笔记
 *   - vidnote_search 给关键词，返回候选视频列表
 *   - vidnote_user   给关键词，返回候选 UP 主（直接请求 B 站搜索接口）
 *
 * 浏览器侧是「对话 / 轨迹」旁边的第三个视图，界面走代理复用 vidnote 自己的
 * serve-ui 接口（进度、关键帧、选目录、打开文件、whisper 依赖都在那边）。
 */
export function apply(ctx, config = {}) {
  const cliPath = resolveCli(config)
  const timeoutMs = Number(config.timeoutMs) || 180_000

  const ui = createUiServer({ cliPath })
  ctx.effect(() => () => ui.stop())

  const api = createHandlers()
  ctx.effect(() => ctx.webServer.register({
    kind: 'exact',
    path: '/vidnote/parse',
    handler: api.parse,
  }))

  // /vidnote/app/api/* → 本地 serve-ui 的 /api/*（流式代理，图片和进度都在里面）
  const proxy = createProxy(async () => {
    await ui.ensure()
    return ui.origin()
  })
  ctx.effect(() => ctx.webServer.register({
    kind: 'prefix',
    path: '/vidnote/app',
    handler: proxy,
  }))

  // 「打开原界面」：起 vidnote 自己的独立窗口（Edge 应用窗口），不是浏览器标签页。
  ctx.effect(() => ctx.webServer.register({
    kind: 'exact',
    path: '/vidnote/window',
    async handler(_req, res) {
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
    },
  }))

  ctx.tools.register(defineTool({
    name: 'vidnote_note',
    description:
      '把 B 站视频抓成一篇带时间戳的 Markdown 笔记（标题、UP 主、分P、字幕或本地转写）。',
    parameters: {
      target: { type: 'string', required: true, description: 'B 站链接、BV 号或 av 号' },
      page: { type: 'number', description: '分P 序号，默认 1' },
      transcribe: {
        type: 'string',
        description:
          "没有字幕时用哪个引擎转写：留空=不转写；'vosk-cn'=Vosk 小模型（42 MB，推荐）；'tiny'/'base'/'small'=whisper",
      },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args, exec) {
      const argv = buildArgs('fetch', args)
      return runVidnote(argv, { cliPath, timeoutMs, signal: exec?.signal })
    },
  }))

  ctx.tools.register(defineTool({
    name: 'vidnote_search',
    description: '按关键词搜索 B 站视频，返回 BV 号、标题、UP 主、时长和播放量（JSON 文本）。',
    parameters: {
      keyword: { type: 'string', required: true, description: '搜索关键词' },
      limit: { type: 'number', description: '返回条数，默认 10' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args, exec) {
      const argv = buildArgs('search', args)
      return runVidnote(argv, { cliPath, timeoutMs, signal: exec?.signal })
    },
  }))

  ctx.tools.register(defineTool({
    name: 'vidnote_user',
    description:
      '按关键词搜索 B 站 UP 主（作者），返回 UID、昵称、粉丝数、投稿数、签名和空间链接（JSON 文本）。',
    parameters: {
      keyword: { type: 'string', required: true, description: '要查的 UP 主昵称或关键词' },
      limit: { type: 'number', description: '返回条数，默认 10，最多 50' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args, exec) {
      const limit = Math.min(Math.max(Number(args.limit) || 10, 1), 50)
      const users = await searchUsers(args.keyword, { limit, signal: exec?.signal })
      return JSON.stringify(users, null, 2)
    },
  }))
}
