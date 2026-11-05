import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { homedir } from 'node:os'

/**
 * 调用 vidnote 命令行，返回 stdout。
 *
 * 单独放在这里（不 import DSH 的任何东西），这样测试不需要安装 DSH。
 */

const DEFAULT_TIMEOUT = 180_000

/** 依次尝试：配置里指定的路径、环境变量、PATH、桌面应用目录。 */
export function resolveCli(config = {}) {
  const candidates = [
    config.cliPath,
    process.env.VIDNOTE_CLI,
    process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, 'vidnote', 'vidnote.exe'),
    process.env.USERPROFILE && join(process.env.USERPROFILE, 'Desktop', 'vidnote-app-full', 'vidnote-server.exe'),
  ].filter(Boolean)

  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate
  }
  // 交给 PATH 解析；找不到时由调用方给出清晰错误。
  return 'vidnote'
}

/** 把工具参数翻译成命令行参数。 */
export function buildArgs(command, args = {}) {
  if (command === 'fetch') {
    const argv = ['fetch', String(args.target ?? '').trim(), '--stdout']
    if (args.page && Number(args.page) > 1) argv.push('--page', String(Number(args.page)))
    if (args.frames && Number(args.frames) > 0) argv.push('--frames', String(Number(args.frames)))
    if (args.transcribe === 'vosk-cn') argv.push('--vosk')
    else if (args.transcribe) argv.push('--whisper', '--model', String(args.transcribe))
    return argv
  }
  if (command === 'search') {
    const argv = ['search', String(args.keyword ?? '').trim(), '--json']
    if (args.limit) argv.push('-n', String(Number(args.limit)))
    return argv
  }
  throw new Error(`unknown command: ${command}`)
}

/**
 * 跑一次 vidnote，返回 stdout 文本。
 * 失败时抛出带 stderr 摘要的错误，方便模型理解发生了什么。
 */
export function runVidnote(argv, { cliPath, timeoutMs = DEFAULT_TIMEOUT, signal, spawnImpl = spawn } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawnImpl(cliPath, argv, {
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    })

    let stdout = ''
    let stderr = ''
    child.stdout?.setEncoding('utf8')
    child.stderr?.setEncoding('utf8')
    child.stdout?.on('data', (chunk) => { stdout += chunk })
    child.stderr?.on('data', (chunk) => { stderr += chunk })

    const timer = setTimeout(() => {
      child.kill()
      reject(new Error(`vidnote 超时（${Math.round(timeoutMs / 1000)} 秒）`))
    }, timeoutMs)

    const onAbort = () => {
      child.kill()
      reject(new Error('已取消'))
    }
    signal?.addEventListener('abort', onAbort, { once: true })

    child.on('error', (error) => {
      clearTimeout(timer)
      signal?.removeEventListener('abort', onAbort)
      reject(new Error(`无法启动 vidnote（${cliPath}）：${error.message}`))
    })

    child.on('close', (code) => {
      clearTimeout(timer)
      signal?.removeEventListener('abort', onAbort)
      if (code === 0) {
        resolve(stdout.trim())
        return
      }
      const detail = (stderr || stdout).trim().split('\n').slice(-3).join(' ')
      reject(new Error(`vidnote 退出码 ${code}${detail ? `：${detail}` : ''}`))
    })
  })
}
