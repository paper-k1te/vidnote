import { spawn } from 'node:child_process'
import { createServer } from 'node:net'

/**
 * vidnote 的「交互窗口」本身就是一个本地网页：`vidnote serve-ui` 会起一个
 * 只监听 127.0.0.1 的 HTTP 服务，页面里带着抓取表单、搜索、进度条和关键帧预览。
 *
 * DSH 插件不重写这套界面，只负责把它拉起来、把地址交给前端，再用 iframe 嵌进
 * 聊天窗口上方。界面自己每 3 秒 ping 一次 `/api/ping`，iframe 一关，服务会在
 * 20 秒后自动退出，不会留下后台进程。
 */

const HOST = '127.0.0.1'

/** 让系统分配一个空闲端口：模拟窗口的 `--port 0` 拿不到端口号。 */
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

/**
 * 管理一个 `vidnote serve-ui` 子进程。
 *
 * @param {object} options
 * @param {string} options.cliPath vidnote 可执行文件
 * @param {Function} [options.spawnImpl] 便于测试
 * @param {Function} [options.fetchImpl] 便于测试
 */
export function createUiServer({
  cliPath,
  spawnImpl = spawn,
  fetchImpl = (...args) => globalThis.fetch(...args),
  env = process.env,
  bootTimeoutMs = 20_000,
  pollMs = 300,
} = {}) {
  let child = null
  let url = ''

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

  function stop() {
    const running = child
    child = null
    url = ''
    if (running) {
      try {
        running.kill()
      } catch {
        // 已经退出
      }
    }
  }

  async function start() {
    stop()
    const port = await freePort()
    const target = `http://${HOST}:${port}/`
    let proc
    try {
      proc = spawnImpl(cliPath, ['serve-ui', '--port', String(port)], {
        stdio: 'ignore',
        windowsHide: true,
        env,
      })
    } catch (error) {
      throw new Error(`无法启动 vidnote 界面服务（${cliPath}）：${error?.message ?? error}`)
    }
    child = proc
    url = target
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
        throw new Error(
          'vidnote 界面服务启动后立即退出。请确认这个 vidnote 版本支持 `serve-ui`（0.3.0 起）。',
        )
      }
      if (await healthy(target)) return target
      await sleep(pollMs)
    }
    stop()
    throw new Error(`vidnote 界面服务启动超时（${Math.round(bootTimeoutMs / 1000)} 秒）。`)
  }

  /** 需要界面时调用：服务还活着就复用，否则拉起一个新的。 */
  async function ensure() {
    if (child && url && (await healthy(url))) return url
    return start()
  }

  return { ensure, stop }
}
