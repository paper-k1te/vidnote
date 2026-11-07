import { spawn } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { mkdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { createServer } from 'node:net'

/**
 * 管理 vidnote 自己的本地界面服务（`vidnote serve-ui`）。
 *
 * 原生界面不自己实现抓取/进度/关键帧，而是把这套接口代理过来：
 *   /vidnote/app/api/*  →  http://127.0.0.1:<port>/api/*
 *
 * 服务自带心跳看门狗：页面不再 ping 之后 20 秒自动退出。DSH 侧只要在「最近用过」
 * 的宽限期内替它 ping 就行，切标签页不会立刻把服务弄死。
 */

const HOST = '127.0.0.1'

/** 默认落盘目录：%LOCALAPPDATA%\vid2note\notes（旧版是 vidnote\notes）。 */
export function notesDir(env = process.env) {
  const base = env.LOCALAPPDATA || join(homedir(), 'AppData', 'Local')
  for (const name of ['vid2note', 'vidnote']) {
    const dir = join(base, name, 'notes')
    try {
      mkdirSync(dir, { recursive: true })
      return dir
    } catch {
      // 换下一个目录名
    }
  }
  return homedir()
}

/** 让系统分配一个空闲端口。 */
export function freePort(host = HOST) {
  return new Promise((resolve, reject) => {
    const server = createServer()
    server.unref()
    server.once('error', reject)
    server.listen(0, host, () => {
      const address = server.address()
      const port = typeof address === 'object' && address ? address.port : 0
      server.close(() => (port ? resolve(port) : reject(new Error('拿不到空闲端口'))))
    })
  })
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export function createUiServer({
  cliPath,
  spawnImpl = spawn,
  fetchImpl = (...args) => globalThis.fetch(...args),
  env = process.env,
  bootTimeoutMs = 20_000,
  pollMs = 300,
  idleGraceMs = 300_000,
  pingEveryMs = 10_000,
} = {}) {
  let child = null
  let url = ''
  let port = 0
  let lastUsed = 0
  let timer = null
  // 每个插件实例一个随机令牌：后端只认它，代理转发时再加上。
  const token = randomBytes(24).toString('hex')

  async function healthy(target) {
    try {
      const response = await fetchImpl(`${target}api/health`, {
        signal: AbortSignal.timeout(1500),
      })
      return Boolean(response?.ok)
    } catch {
      return false
    }
  }

  function touch() {
    lastUsed = Date.now()
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    const running = child
    child = null
    url = ''
    port = 0
    if (running) {
      try {
        running.kill()
      } catch {
        // 已经退出
      }
    }
  }

  function startHeartbeat() {
    if (timer) return
    timer = setInterval(() => {
      if (!child || Date.now() - lastUsed > idleGraceMs) return
      fetchImpl(`${url}api/ping`, { signal: AbortSignal.timeout(2000) }).catch(() => {})
    }, pingEveryMs)
    timer.unref?.()
  }

  async function start() {
    stop()
    port = await freePort()
    const target = `http://${HOST}:${port}/`
    let proc
    try {
      proc = spawnImpl(cliPath, ['serve-ui', '--port', String(port), '--token', token], {
        stdio: 'ignore',
        windowsHide: true,
        env,
        cwd: notesDir(env),
      })
    } catch (error) {
      throw new Error(`无法启动 vidnote 界面服务（${cliPath}）：${error?.message ?? error}`)
    }
    child = proc
    url = target
    touch()
    startHeartbeat()
    proc?.on?.('error', () => {
      if (child === proc) {
        child = null
        url = ''
      }
    })
    proc?.on?.('exit', () => {
      if (child === proc) {
        child = null
        url = ''
      }
    })

    const deadline = Date.now() + bootTimeoutMs
    while (Date.now() < deadline) {
      if (child !== proc) {
        throw new Error('vidnote 界面服务启动后立即退出，请确认这个版本支持 `serve-ui`（0.3.0 起）。')
      }
      if (await healthy(target)) return target
      await sleep(pollMs)
    }
    stop()
    throw new Error(`vidnote 界面服务启动超时（${Math.round(bootTimeoutMs / 1000)} 秒）。`)
  }

  async function ensure() {
    if (child && url && (await healthy(url))) {
      touch()
      return url
    }
    return start()
  }

  function origin() {
    return { url, port }
  }

  return { ensure, touch, stop, origin, token }
}
