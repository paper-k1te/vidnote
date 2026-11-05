import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { existsSync } from 'node:fs'
import { test } from 'node:test'
import { buildArgs, resolveCli, runVidnote } from '../lib/run.js'

/** 假子进程：stdout/stderr 是可写事件流，kill 可被观察。 */
function makeChild() {
  const child = new EventEmitter()
  child.stdout = new EventEmitter()
  child.stderr = new EventEmitter()
  child.stdout.setEncoding = () => {}
  child.stderr.setEncoding = () => {}
  child.killed = false
  child.kill = () => { child.killed = true }
  return child
}

/** 按预设输出并在下一轮事件循环退出。 */
function fakeChild({ stdout = '', stderr = '', code = 0 } = {}) {
  const child = makeChild()
  setImmediate(() => {
    if (stdout) child.stdout.emit('data', stdout)
    if (stderr) child.stderr.emit('data', stderr)
    child.emit('close', code)
  })
  return child
}

test('fetch 参数：默认只带 --stdout', () => {
  assert.deepEqual(buildArgs('fetch', { target: ' BV1xx ' }), ['fetch', 'BV1xx', '--stdout'])
})

test('fetch 参数：分P、关键帧、转写引擎', () => {
  assert.deepEqual(
    buildArgs('fetch', { target: 'BV1', page: 2, frames: 4, transcribe: 'vosk-cn' }),
    ['fetch', 'BV1', '--stdout', '--page', '2', '--frames', '4', '--vosk'],
  )
  assert.deepEqual(
    buildArgs('fetch', { target: 'BV1', transcribe: 'small' }),
    ['fetch', 'BV1', '--stdout', '--whisper', '--model', 'small'],
  )
})

test('search 参数带 --json', () => {
  assert.deepEqual(buildArgs('search', { keyword: 'python', limit: 5 }), [
    'search',
    'python',
    '--json',
    '-n',
    '5',
  ])
})

test('未知命令直接报错', () => {
  assert.throws(() => buildArgs('nope', {}), /unknown command/)
})

test('resolveCli 优先用配置里的路径', () => {
  assert.equal(resolveCli({ cliPath: process.execPath }), process.execPath)
})

test('resolveCli 忽略不存在的路径，回落到可用项', () => {
  const cli = resolveCli({ cliPath: 'C:/definitely/not/here.exe' })
  // 仓库里构建过时会命中本地产物，没构建过则回落到 PATH 上的 vidnote。
  assert.ok(cli === 'vidnote' || existsSync(cli), `unexpected: ${cli}`)
})

test('runVidnote 返回 stdout 并去掉尾部空白', async () => {
  const text = await runVidnote(['version'], {
    cliPath: 'vidnote',
    spawnImpl: () => fakeChild({ stdout: 'vidnote 0.3.1\n' }),
  })
  assert.equal(text, 'vidnote 0.3.1')
})

test('runVidnote 非零退出时把 stderr 带上', async () => {
  await assert.rejects(
    runVidnote(['fetch', 'bad'], {
      cliPath: 'vidnote',
      spawnImpl: () => fakeChild({ code: 1, stderr: '无法识别的视频标识' }),
    }),
    /退出码 1：无法识别的视频标识/,
  )
})

test('runVidnote 超时会杀掉进程', async () => {
  const child = makeChild()
  await assert.rejects(
    runVidnote(['fetch', 'BV1'], { cliPath: 'vidnote', timeoutMs: 20, spawnImpl: () => child }),
    /超时/,
  )
  assert.equal(child.killed, true)
})

test('runVidnote 启动失败给出清晰错误', async () => {
  const child = makeChild()
  setImmediate(() => child.emit('error', new Error('ENOENT')))
  await assert.rejects(
    runVidnote(['version'], { cliPath: 'vidnote', spawnImpl: () => child }),
    /无法启动 vidnote/,
  )
})
