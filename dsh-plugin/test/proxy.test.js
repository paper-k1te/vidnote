import assert from 'node:assert/strict'
import { createServer, request } from 'node:http'
import { test } from 'node:test'
import { createProxy, upstreamPath } from '../lib/proxy.js'

test('upstreamPath 还原成 vidnote 服务上的路径', () => {
  assert.equal(upstreamPath('/vidnote/app/api/health'), '/api/health')
  assert.equal(upstreamPath('/vidnote/app/api/frame?note=a&src=b'), '/api/frame?note=a&src=b')
  assert.equal(upstreamPath('/vidnote/app'), '/')
  assert.equal(upstreamPath('/vidnote/app/'), '/')
  assert.equal(upstreamPath(undefined), '/')
})

test('upstreamPath 不动别的路径', () => {
  assert.equal(upstreamPath('/api/health'), '/api/health')
})

function listen(server) {
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server.address().port)))
}

function close(server) {
  return new Promise((resolve) => server.close(resolve))
}

test('代理把 chunked 请求体补成 Content-Length 再转发', async () => {
  let received = ''
  let contentLength = ''
  const target = createServer((req, res) => {
    contentLength = String(req.headers['content-length'] ?? '')
    req.on('data', (chunk) => {
      received += chunk
    })
    req.on('end', () => {
      res.writeHead(200, { 'content-type': 'application/json' })
      res.end(JSON.stringify({ ok: true }))
    })
  })
  const targetPort = await listen(target)

  const proxy = createProxy(async () => ({ port: targetPort }))
  const front = createServer((req, res) => {
    proxy(req, res)
  })
  const frontPort = await listen(front)

  const payload = JSON.stringify({ target: 'BV1qS4b61EKU' })
  const response = await new Promise((resolve, reject) => {
    const req = request(
      {
        hostname: '127.0.0.1',
        port: frontPort,
        path: '/vidnote/app/api/fetch',
        method: 'POST',
        headers: { 'content-type': 'application/json', 'transfer-encoding': 'chunked' },
      },
      (res) => {
        let text = ''
        res.on('data', (chunk) => {
          text += chunk
        })
        res.on('end', () => resolve({ status: res.statusCode, text }))
      },
    )
    req.on('error', reject)
    req.write(payload)
    req.end()
  })

  assert.equal(response.status, 200)
  assert.equal(received, payload)
  assert.equal(contentLength, String(Buffer.byteLength(payload)))

  await close(front)
  await close(target)
})

test('代理注入后端令牌，并覆盖客户端伪造的值', async () => {
  let seen = ''
  const target = createServer((req, res) => {
    seen = String(req.headers['x-vidnote-token'] ?? '')
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end('{}')
  })
  const targetPort = await listen(target)

  const proxy = createProxy(async () => ({ port: targetPort }), { token: 'host-token' })
  const front = createServer((req, res) => {
    proxy(req, res)
  })
  const frontPort = await listen(front)

  await new Promise((resolve, reject) => {
    const req = request(
      {
        hostname: '127.0.0.1',
        port: frontPort,
        path: '/vidnote/app/api/health',
        headers: { 'x-vidnote-token': 'forged' },
      },
      (res) => {
        res.resume()
        res.on('end', resolve)
      },
    )
    req.on('error', reject)
    req.end()
  })

  assert.equal(seen, 'host-token')
  await close(front)
  await close(target)
})
