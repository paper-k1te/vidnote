import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { test } from 'node:test'
import { createUiServer } from '../lib/ui.js'

function fakeChild() {
  const child = new EventEmitter()
  child.killed = false
  child.kill = () => {
    child.killed = true
    child.emit('exit')
  }
  return child
}

function fakeSpawn(child) {
  const calls = []
  const spawnImpl = (command, args, options) => {
    calls.push({ command, args, options })
    return child
  }
  return { spawnImpl, calls }
}

test('ensure 启动 serve-ui 并等到健康检查通过', async () => {
  const child = fakeChild()
  const { spawnImpl, calls } = fakeSpawn(child)
  let checks = 0
  const ui = createUiServer({
    cliPath: 'vidnote',
    spawnImpl,
    fetchImpl: async () => ({ ok: ++checks > 1 }),
    pollMs: 1,
    env: {},
  })

  const url = await ui.ensure()
  assert.match(url, /^http:\/\/127\.0\.0\.1:\d+\/$/)
  assert.equal(calls.length, 1)
  assert.deepEqual(calls[0].args.slice(0, 1), ['serve-ui'])
  assert.equal(calls[0].options.stdio, 'ignore')
  ui.stop()
  assert.equal(child.killed, true)
})

test('服务还活着时复用同一个进程', async () => {
  const child = fakeChild()
  const { spawnImpl, calls } = fakeSpawn(child)
  const ui = createUiServer({
    cliPath: 'vidnote',
    spawnImpl,
    fetchImpl: async () => ({ ok: true }),
    pollMs: 1,
    env: {},
  })
  const first = await ui.ensure()
  const second = await ui.ensure()
  assert.equal(first, second)
  assert.equal(calls.length, 1)
  ui.stop()
})

test('子进程启动后立刻退出时给出可读错误', async () => {
  const child = fakeChild()
  const { spawnImpl } = fakeSpawn(child)
  const ui = createUiServer({
    cliPath: 'vidnote',
    spawnImpl,
    fetchImpl: async () => {
      child.emit('exit')
      return { ok: false }
    },
    pollMs: 1,
    env: {},
  })
  await assert.rejects(ui.ensure(), /serve-ui/)
})
