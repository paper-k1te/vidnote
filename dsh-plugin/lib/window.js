import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * 打开 vid2note 自己的独立窗口。
 *
 * 0.3.4 起桌面端换成了 Tauri（vidnote-desktop.exe），直接启动它即可；
 * 老版本只有 `vidnote gui --app`（Edge 应用窗口）这一条路，作为兜底保留。
 * 进程 detach 掉，DSH 不管它的生命周期。
 */

const PLUGIN_DIR = dirname(dirname(fileURLToPath(import.meta.url)))

export function appWindowArgs() {
  return ['gui', '--app']
}

/** 按优先级列出可能的 Tauri 桌面端可执行文件。 */
export function desktopCandidates(env = process.env, home = homedir()) {
  return [
    env.VID2NOTE_APP,
    env.VIDNOTE_APP,
    join(PLUGIN_DIR, '..', 'src-tauri', 'target', 'release', 'vid2note-desktop.exe'),
    join(PLUGIN_DIR, '..', 'src-tauri', 'target', 'release', 'vidnote-desktop.exe'),
    join(PLUGIN_DIR, '..', 'dist-app', 'vid2note.exe'),
    join(PLUGIN_DIR, '..', 'dist-app', 'vidnote.exe'),
    env.LOCALAPPDATA && join(env.LOCALAPPDATA, 'vid2note', 'vid2note.exe'),
    env.LOCALAPPDATA && join(env.LOCALAPPDATA, 'Programs', 'vid2note', 'vid2note.exe'),
    env.LOCALAPPDATA && join(env.LOCALAPPDATA, 'vidnote', 'vidnote.exe'),
    join(home, 'Desktop', 'vid2note-app.exe'),
    join(home, 'Desktop', 'vidnote-app.exe'),
  ].filter(Boolean)
}

export function openAppWindow({
  cliPath,
  spawnImpl = spawn,
  env = process.env,
  exists = existsSync,
  home = homedir(),
} = {}) {
  const desktop = desktopCandidates(env, home).find((candidate) => exists(candidate))

  const [command, args] = desktop ? [desktop, []] : [cliPath, appWindowArgs()]
  if (!command) throw new Error('没有可用的 vid2note 桌面端或命令行，无法打开独立窗口。')

  const child = spawnImpl(command, args, {
    detached: true,
    stdio: 'ignore',
    windowsHide: false,
    env,
  })
  child?.unref?.()
  return desktop ? 'desktop' : 'cli'
}
