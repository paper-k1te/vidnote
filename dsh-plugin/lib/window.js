import { spawn } from 'node:child_process'

/**
 * 打开 vidnote 自己的独立窗口（Edge 应用窗口模式），而不是浏览器标签页。
 *
 * `vidnote gui --app` 会先起一个本地服务，再用系统自带的 Edge/Chrome 应用窗口
 * 打开原界面；窗口关掉后服务会自己退出。这里 detach 掉，DSH 不用管它的生命周期。
 */

export function appWindowArgs() {
  return ['gui', '--app']
}

export function openAppWindow({ cliPath, spawnImpl = spawn, env = process.env } = {}) {
  if (!cliPath) throw new Error('没有配置 vidnote 可执行文件，无法打开独立窗口。')
  const child = spawnImpl(cliPath, appWindowArgs(), {
    detached: true,
    stdio: 'ignore',
    windowsHide: false,
    env,
  })
  child?.unref?.()
  return true
}
