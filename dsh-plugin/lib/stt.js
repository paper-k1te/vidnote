import { createServer } from 'node:http'
import { randomBytes } from 'node:crypto'

/**
 * 把 DSH 自带的语音输入（ctx.speechToText + 本地 SenseVoice）借给 vid2note 后端用。
 *
 * 后端是独立进程，拿不到 Cordis 的 ctx，所以这里在 127.0.0.1 开一个只认随机
 * token 的小 HTTP 端点：后端把 16 kHz 单声道 WAV 切片 POST 过来，这里调用
 * speechToText 转写，再把纯文本返回去。
 *
 * 没有启用 voice-input bundle 时服务不存在，端点返回 503 并带上原因。
 */

const MAX_BYTES = 64 * 1024 * 1024
const PREPARE_TIMEOUT_MS = 20 * 60 * 1000

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** 选一个可用的 provider，必要时等它下载/加载完成。 */
async function ensureProvider(service) {
  const snapshot = () => service.snapshot()
  let state = snapshot()
  const providers = state?.providers ?? []
  if (!providers.length) {
    throw new Error('宿主没有语音识别 provider：请先在插件管理器里启用 Voice Input（本地 SenseVoice）')
  }
  const wanted = state?.selection?.providerId
  const provider = providers.find((item) => item.id === wanted)
    ?? providers.find((item) => item.location === 'host-local')
    ?? providers[0]

  let phase = provider.preparation?.phase
  if (phase === 'ready') return provider

  if (phase === 'failed') {
    throw new Error(`本地语音模型不可用：${provider.preparation?.message || '准备失败'}`)
  }

  service.prepare(provider.id)
  const deadline = Date.now() + PREPARE_TIMEOUT_MS
  while (Date.now() < deadline) {
    await sleep(1000)
    state = snapshot()
    const next = state?.providers?.find((item) => item.id === provider.id)
    phase = next?.preparation?.phase
    if (phase === 'ready') return next
    if (phase === 'failed') {
      throw new Error(`本地语音模型准备失败：${next?.preparation?.message || '未知原因'}`)
    }
  }
  throw new Error('等待本地语音模型下载超时（20 分钟）')
}

/**
 * @param {import('@deepseek-ai/cordis').Context} ctx
 */
export function createSttServer(ctx, { prepareTimeoutMs = PREPARE_TIMEOUT_MS } = {}) {
  const token = randomBytes(18).toString('hex')
  let origin = ''
  const server = createServer(async (req, res) => {
    const url = new URL(req.url || '/', 'http://127.0.0.1')
    if (url.pathname !== '/transcribe') {
      res.writeHead(404).end()
      return
    }
    if (req.method !== 'POST') {
      res.writeHead(405).end()
      return
    }
    if (req.headers['x-vidnote-token'] !== token) {
      res.writeHead(401).end()
      return
    }

    const chunks = []
    let size = 0
    for await (const chunk of req) {
      size += chunk.length
      if (size > MAX_BYTES) {
        res.writeHead(413).end()
        return
      }
      chunks.push(chunk)
    }

    try {
      const service = ctx.get?.('speechToText')
      if (!service) {
        throw new Error('宿主没有启用语音输入（speechToText 服务不存在）')
      }
      const provider = await ensureProviderWithTimeout(service, prepareTimeoutMs)
      const audio = new Uint8Array(Buffer.concat(chunks))
      const spec = service.resolve({ audio, providerId: provider.id })
      const transcript = await service.transcribe(spec, AbortSignal.timeout(30 * 60 * 1000))
      res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' })
      res.end(JSON.stringify({
        text: transcript.text,
        seconds: transcript.audioSeconds,
        provider: provider.id,
      }))
    } catch (error) {
      res.writeHead(503, { 'content-type': 'application/json; charset=utf-8' })
      res.end(JSON.stringify({ error: String(error?.message ?? error) }))
    }
  })

  const ready = new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      origin = `http://127.0.0.1:${server.address().port}/transcribe`
      resolve()
    })
  })

  return {
    token,
    ready,
    get url() {
      return origin
    },
    stop() {
      return new Promise((resolve) => server.close(() => resolve()))
    },
  }
}

/** 带超时的 prepare 包装，方便单测传更短的值。 */
function ensureProviderWithTimeout(service, timeoutMs) {
  if (timeoutMs === PREPARE_TIMEOUT_MS) return ensureProvider(service)
  return (async () => {
    const snapshot = () => service.snapshot()
    let state = snapshot()
    const providers = state?.providers ?? []
    if (!providers.length) throw new Error('宿主没有语音识别 provider')
    const provider = providers.find((item) => item.id === state?.selection?.providerId) ?? providers[0]
    if (provider.preparation?.phase === 'ready') return provider
    service.prepare(provider.id)
    const deadline = Date.now() + timeoutMs
    while (Date.now() < deadline) {
      await sleep(50)
      state = snapshot()
      const next = state?.providers?.find((item) => item.id === provider.id)
      if (next?.preparation?.phase === 'ready') return next
      if (next?.preparation?.phase === 'failed') throw new Error(next?.preparation?.message || '准备失败')
    }
    throw new Error('等待本地语音模型超时')
  })()
}
