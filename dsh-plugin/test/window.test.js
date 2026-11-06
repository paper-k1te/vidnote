import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { test } from 'node:test'
import { appWindowArgs, desktopCandidates, openAppWindow } from '../lib/window.js'

function fakeSpawn() {
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
  return { child, calls, spawnImpl }
}

test('有 Tauri 桌面端时直接启动它', () => {
  const { child, calls, spawnImpl } = fakeSpawn()
  const result = openAppWindow({
    cliPath: 'vid2note',
    spawnImpl,
    env: { VID2NOTE_APP: 'C:/Apps/vid2note.exe' },
    exists: (candidate) => candidate === 'C:/Apps/vid2note.exe',
    home: 'C:/Users/test',
  })

  assert.equal(result, 'desktop')
  assert.equal(calls[0].command, 'C:/Apps/vid2note.exe')
  assert.deepEqual(calls[0].args, [])
  assert.equal(calls[0].options.detached, true)
  assert.equal(child.unrefCalled, true)
})

test('没有桌面端时退回 gui --app', () => {
  const { calls, spawnImpl } = fakeSpawn()
  const result = openAppWindow({
    cliPath: 'vid2note',
    spawnImpl,
    env: {},
    exists: () => false,
    home: 'C:/Users/test',
  })

  assert.equal(result, 'cli')
  assert.equal(calls[0].command, 'vid2note')
  assert.deepEqual(calls[0].args, ['gui', '--app'])
  assert.deepEqual(appWindowArgs(), ['gui', '--app'])
})

test('desktopCandidates 覆盖仓库构建和本地安装', () => {
  const candidates = desktopCandidates({ LOCALAPPDATA: 'C:/L' }, 'C:/Users/test')
  assert.ok(candidates.some((item) => item.endsWith('vid2note-desktop.exe')))
  assert.ok(candidates.some((item) => item.endsWith('vidnote-desktop.exe')))
  assert.ok(candidates.some((item) => item.includes('Apps') === false && item.endsWith('vid2note.exe')))
})

test('没有可执行文件时报错', () => {
  assert.throws(() => openAppWindow({ env: {}, exists: () => false }), /桌面端/)
})
