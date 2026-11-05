import { defineTool } from '@deepseek-ai/dsh-tools'
import { searchUsers } from './lib/bili.js'
import { buildArgs, resolveCli, runVidnote } from './lib/run.js'
import { createUiServer } from './lib/ui.js'

export const name = 'dsh-vidnote'
export const inject = ['tools', 'webServer']

/**
 * 把 vidnote 接到 DSH 里：模型可以直接抓 B 站视频、搜视频/搜 UP 主，拿到带时间戳的 Markdown。
 *
 * 模型不直接跑命令行，只看到三个工具：
 *   - vidnote_note   给链接/BV 号，返回整篇笔记
 *   - vidnote_search 给关键词，返回候选视频列表
 *   - vidnote_user   给关键词，返回候选 UP 主（直接请求 B 站搜索接口）
 */
export function apply(ctx, config = {}) {
  const cliPath = resolveCli(config)
  const timeoutMs = Number(config.timeoutMs) || 180_000

  const ui = createUiServer({ cliPath })
  ctx.effect(() => () => ui.stop())

  // 浏览器里的「B站笔记」按钮通过这个路由拿本地界面地址。服务只监听 127.0.0.1。
  ctx.effect(() => ctx.webServer.register({
    kind: 'exact',
    path: '/vidnote/url',
    async handler(_req, res) {
      try {
        const url = await ui.ensure()
        res.writeHead(200, {
          'content-type': 'application/json; charset=utf-8',
          'cache-control': 'no-store',
        })
        res.end(JSON.stringify({ url }))
      } catch (error) {
        res.writeHead(503, {
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
      '把 B 站视频抓成一篇带时间戳的 Markdown 笔记（标题、UP 主、分P、字幕/转写、可选关键帧）。',
    parameters: {
      target: { type: 'string', required: true, description: 'B 站链接、BV 号或 av 号' },
      page: { type: 'number', description: '分P 序号，默认 1' },
      frames: { type: 'number', description: '导出关键帧张数，0 表示不抽' },
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
