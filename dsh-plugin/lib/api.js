import { parseNote } from './markdown.js'

/** 原生界面用到的小接口：读 JSON body、回 JSON、把笔记解析成块。 */

const MAX_BODY = 64 * 1024

export function send(res, status, payload) {
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

/** POST /vidnote/parse：把 Markdown 解析成块，交给前端渲染（带关键帧图片节点）。 */
export function createHandlers() {
  return {
    async parse(req, res) {
      const body = await readJson(req)
      const markdown = String(body.markdown ?? '')
      if (!markdown.trim()) {
        send(res, 400, { error: '没有可解析的内容。' })
        return
      }
      const note = parseNote(markdown)
      send(res, 200, { meta: note.meta, blocks: note.blocks })
    },
  }
}
