import { request } from 'node:http'

/** 把 `/vidnote/app/api/...` 还原成 vidnote 服务上的 `/api/...`。 */
export function upstreamPath(rawUrl) {
  const value = String(rawUrl ?? '')
  const stripped = value.replace(/^\/vidnote\/app/, '')
  return stripped || '/'
}

/**
 * 反向代理到 `vidnote serve-ui` 起的本地服务。
 *
 * 前端只用同源 `/vidnote/app/*`，这样搜索、抓取任务、进度轮询、关键帧图片、
 * 选目录、打开文件全都复用 vidnote 自己的实现，不用在 JS 里重写一遍。
 */
export function createProxy(resolveOrigin) {
  return async function proxy(req, res) {
    let origin
    try {
      origin = await resolveOrigin()
    } catch (error) {
      if (!res.headersSent) {
        res.writeHead(503, { 'content-type': 'application/json; charset=utf-8' })
        res.end(JSON.stringify({ error: String(error?.message ?? error) }))
      }
      return
    }

    const headers = { ...req.headers, host: `127.0.0.1:${origin.port}` }
    const upstream = request(
      {
        hostname: '127.0.0.1',
        port: origin.port,
        path: upstreamPath(req.url),
        method: req.method,
        headers,
      },
      (response) => {
        res.writeHead(response.statusCode ?? 502, response.headers)
        response.pipe(res)
      },
    )

    upstream.on('error', (error) => {
      if (!res.headersSent) {
        res.writeHead(502, { 'content-type': 'application/json; charset=utf-8' })
        res.end(JSON.stringify({ error: `vidnote 服务不可用：${error?.message ?? error}` }))
      } else {
        res.destroy()
      }
    })

    req.pipe(upstream)
  }
}
