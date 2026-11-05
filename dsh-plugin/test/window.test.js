import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { test } from 'node:test'
import { appWindowArgs, openAppWindow } from '../lib/window.js'

test('独立窗口用 gui --app 启动并且 detach', () => {
  const child = new EventEmitter()
  child.unrefCalled = false
  child.unref = () => {
    child.unrefCalled = true
  }
  const calls = []
  const spawnImpl = (command, args, options) => {
    calls.push({ command, args, options })
    return child
  }

  assert.equal(openAppWindow({ cliPath: 'vidnote', spawnImpl, env: {} }), true)
  assert.deepEqual(calls[0].args, ['gui', '--app'])
  assert.equal(calls[0].options.detached, true)
  assert.equal(calls[0].options.stdio, 'ignore')
  assert.equal(child.unrefCalled, true)
  assert.deepEqual(appWindowArgs(), ['gui', '--app'])
})

test('没有可执行文件时报错', () => {
  assert.throws(() => openAppWindow({}), /可执行文件/)
})
