import { spawn } from 'node:child_process'
import { existsSync, readdirSync, unlinkSync, writeFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { homedir, tmpdir } from 'node:os'

/**
 * 调用 vidnote 命令行，返回 stdout。
 *
 * 单独放在这里（不 import DSH 的任何东西），这样测试不需要安装 DSH。
 */

const DEFAULT_TIMEOUT = 180_000

const PLUGIN_DIR = dirname(dirname(fileURLToPath(import.meta.url)))

/** 找一个确实**可写**的临时目录：TEMP 被清空的进程里 os.tmpdir() 也会返回空串，
 *  而 %SystemRoot%\Temp 存在但普通用户写不进去。 */
export function scratchDir() {
  const candidates = [
    process.env.TEMP,
    process.env.TMP,
    tmpdir(),
    process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, 'Temp'),
    process.env.USERPROFILE && join(process.env.USERPROFILE, 'AppData', 'Local', 'Temp'),
    process.env.SystemRoot && join(process.env.SystemRoot, 'Temp'),
  ]
  for (const candidate of candidates) {
    if (!candidate) continue
    try {
      const probe = join(candidate, `.vidnote-probe-${process.pid}`)
      writeFileSync(probe, '')
      unlinkSync(probe)
      return candidate
    } catch {
      // 不存在或没权限，试下一个
    }
  }
  return tmpdir()
}

/** 桌面版解压出来的目录名前缀，例如 vidnote-app-full-0.2.3。 */
const DESKTOP_APP_PREFIX = 'vidnote-app'

/** 在桌面目录里找解压好的桌面版（目录名带版本号，只能扫）。 */
function desktopApps(home = homedir(), readdir = readdirSync) {
  const found = []
  for (const desktop of [join(home, 'Desktop'), join(home, 'OneDrive', 'Desktop')]) {
    let entries = []
    try {
      entries = readdir(desktop, { withFileTypes: true })
    } catch {
      continue
    }
    for (const entry of entries) {
      if (!entry.isDirectory() || !entry.name.startsWith(DESKTOP_APP_PREFIX)) continue
      for (const exe of ['vidnote-server.exe', 'vidnote.exe']) {
        const candidate = join(desktop, entry.name, exe)
        if (existsSync(candidate)) found.push(candidate)
      }
    }
  }
  return found
}

/** 依次尝试：配置、环境变量、仓库里的构建产物、常见安装位置、桌面版、PATH。 */
export function resolveCli(config = {}, env = process.env, readdir = readdirSync) {
  const candidates = [
    config.cliPath,
    env.VIDNOTE_CLI,
    // 从仓库里直接 link 进来时，构建产物就在隔壁（开发场景最常见）
    join(PLUGIN_DIR, '..', 'dist-exe-full', 'vidnote-server.exe'),
    join(PLUGIN_DIR, '..', 'dist-exe', 'vidnote.exe'),
    env.LOCALAPPDATA && join(env.LOCALAPPDATA, 'vidnote', 'vidnote.exe'),
    env.LOCALAPPDATA && join(env.LOCALAPPDATA, 'Programs', 'vidnote', 'vidnote.exe'),
    env.USERPROFILE && join(env.USERPROFILE, 'Desktop', 'vidnote-app-full', 'vidnote-server.exe'),
    ...desktopApps(env.USERPROFILE || homedir(), readdir),
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
    // `--stdout` 只输出文本，vidnote 会跳过关键帧；传 `--frames` 只会让进程以 1 退出。
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
      // 单文件 exe 启动时要解压到 %TEMP%；变量缺失或被清空的进程里会直接报
      // "Could not create temporary directory"，这里兜一个默认值。
      env: { ...process.env, TEMP: scratchDir(), TMP: scratchDir() },
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
      if (error.code === 'ENOENT') {
        reject(new Error(
          `找不到 vidnote 命令行（尝试执行「${cliPath}」）。\n` +
          '请任选一种方式指定：\n' +
          '  1. 设置环境变量 VIDNOTE_CLI 指向 vidnote.exe 或 vidnote-server.exe；\n' +
          '  2. 在 profile 的 cordis.patch.yml 里给 dsh-vidnote 配置 cliPath；\n' +
          '  3. 把 vidnote 加到 PATH。',
        ))
        return
      }
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
      // 单文件 exe 启动时要解压到临时目录；目录不可写或 exe 带低完整性标签时，
      // PyInstaller 只会吐一行 PYI-xxxx 错误，模型看不出该怎么办。
      if (/PYI-\d+:ERROR\].*(temporary directory|parent directory)/i.test(detail)) {
        reject(new Error(
          'vidnote 无法解压运行环境：单文件 exe 需要可写的临时目录。\n' +
          '请把 TEMP/TMP 指向可写目录，或把 vidnote 可执行文件移到普通目录（不要放在带低完整性标签的沙箱目录）后重试。\n' +
          `原始输出：${detail}`,
        ))
        return
      }
      reject(new Error(`vidnote 退出码 ${code}${detail ? `：${detail}` : ''}`))
    })
  })
}
