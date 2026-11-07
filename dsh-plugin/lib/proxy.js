import { request } from 'node:http'

/** 把 `/vidnote/app/api/...` 还原成 vidnote 服务上的 `/api/...`。 */
export function upstreamPath(rawUrl) {
  const value = String(rawUrl ?? '')
  const stripped = value.replace(/^\/vidnote\/app/, '')
  return stripped || '/'
}

const MAX_BODY = 2 * 1024 * 1024

/** 收完整个请求体：浏览器可能用 chunked，vidnote 的 Python 端只认 Content-Length。 */
function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = []
    let size = 0
    req.on('data', (chunk) => {
      size += chunk.length
      if (size > MAX_BODY) {
        reject(new Error('请求体太大'))
        req.destroy()
        return
      }
      chunks.push(chunk)
    })
    req.on('end', () => resolve(Buffer.concat(chunks)))
    req.on('error', reject)
  })
}

/**
 * 反向代理到 `vidnote serve-ui` 起的本地服务。
 *
 * 前端只用同源 `/vidnote/app/*`，这样搜索、抓取任务、进度轮询、关键帧图片、
 * 选目录、打开文件全都复用 vidnote 自己的实现，不用在 JS 里重写一遍。
 *
 * 请求体先缓冲再转发：vidnote 的 `BaseHTTPRequestHandler` 用 Content-Length 读体，
 * 直接 `req.pipe()` 一个 chunked 请求会让它以为没有 body（表现就是「请输入 B 站
 * 视频链接、BV 号或 av 号」）。
 */
export function createProxy(resolveOrigin) {
  return async function proxy(req, res) {
    let body
    try {
      body = await readBody(req)
    } catch (error) {
      if (!res.headersSent) {
        res.writeHead(413, { 'content-type': 'application/json; charset=utf-8' })
        res.end(JSON.stringify({ error: String(error?.message ?? error) }))
      }
      return
    }

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
    delete headers['transfer-encoding']
    delete headers['content-length']
    headers['content-length'] = String(body.length)

    const upstream = request(
      {
        hostname: '127.0.0.1',
        port: origin.port,
        path: upstreamPath(req.url),
        method: req.method,
        headers,
      },
      (response) => {
        // 后端给的是宽松 CORS；经过宿主代理后同源访问即可，去掉这些头，
        // 避免别的站点借 * 直接调本地接口。
        const headers = { ...response.headers }
        for (const name of [
          'access-control-allow-origin',
          'access-control-allow-credentials',
          'access-control-allow-methods',
          'access-control-allow-headers',
        ]) {
          delete headers[name]
        }
        res.writeHead(response.statusCode ?? 502, headers)
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

    upstream.end(body)
  }
}
