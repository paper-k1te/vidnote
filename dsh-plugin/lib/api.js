import { searchUsers, searchVideos } from './bili.js'
import { parseNote } from './markdown.js'
import { buildArgs, runVidnote } from './run.js'

/**
 * 给原生界面用的 JSON 接口（`/vidnote/api/*`）。都是本机 127.0.0.1 上的路由，
 * 由 DSH 的 web server 提供，前端用同源 fetch 调用。
 */

const MAX_BODY = 64 * 1024

function send(res, status, payload) {
  const body = JSON.stringify(payload)
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
  })
  res.end(body)
}

/** 读一个不超过 64 KiB 的 JSON body；读不出来就当空对象。 */
export function readJson(req, limit = MAX_BODY) {
  return new Promise((resolve) => {
    let size = 0
    const chunks = []
    req.on('data', (chunk) => {
      size += chunk.length
      if (size <= limit) chunks.push(chunk)
    })
    req.on('end', () => {
      if (!chunks.length) {
        resolve({})
        return
      }
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')))
      } catch {
        resolve({})
      }
    })
    req.on('error', () => resolve({}))
  })
}

export function createHandlers({
  cliPath,
  timeoutMs = 180_000,
  fetchImpl = globalThis.fetch,
  run = runVidnote,
} = {}) {
  return {
    async search(req, res) {
      const body = await readJson(req)
      const keyword = String(body.keyword ?? '').trim()
      if (!keyword) {
        send(res, 400, { error: '搜索关键词不能为空。' })
        return
      }
      const limit = Math.min(Math.max(Number(body.limit) || 10, 1), 50)
      try {
        if (body.type === 'user') {
          send(res, 200, { users: await searchUsers(keyword, { limit, fetchImpl }) })
        } else {
          send(res, 200, { videos: await searchVideos(keyword, { limit, fetchImpl }) })
        }
      } catch (error) {
        send(res, 502, { error: String(error?.message ?? error) })
      }
    },

    async fetch(req, res) {
      const body = await readJson(req)
      const target = String(body.target ?? '').trim()
      if (!target) {
        send(res, 400, { error: '请先填入 B 站链接、BV 号或 av 号。' })
        return
      }

      const controller = new AbortController()
      res.on('close', () => {
        if (!res.writableEnded) controller.abort()
      })

      const argv = buildArgs('fetch', {
        target,
        page: body.page,
        frames: body.frames,
        transcribe: body.transcribe,
      })

      try {
        const markdown = await run(argv, {
          cliPath,
          timeoutMs,
          signal: controller.signal,
        })
        const note = parseNote(markdown)
        send(res, 200, { markdown, meta: note.meta, blocks: note.blocks, target })
      } catch (error) {
        send(res, 502, { error: String(error?.message ?? error) })
      }
    },
  }
}
