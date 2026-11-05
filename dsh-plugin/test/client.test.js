import assert from 'node:assert/strict'
import { test } from 'node:test'

/** 用一个假的 React 和假的加载器，验证客户端模块的接线（不渲染 DOM）。 */
test('client.js 注册到 shell.overlay', async () => {
  let captured
  globalThis.window = {
    __ModuleLoader__: {
      load(definition) {
        captured = definition
      },
    },
  }

  await import('../client.js')

  assert.equal(captured.id, 'dsh-vidnote')
  assert.equal(typeof captured.factory, 'function')

  const React = {
    createElement: (...args) => args,
    Fragment: Symbol('Fragment'),
    useState: (value) => [value, () => {}],
    useEffect: () => {},
  }
  const module = captured.factory((name) => {
    if (name === 'react') return React
    if (name === 'react-dom') return { createPortal: (node) => node }
    throw new Error(`unexpected module: ${name}`)
  })

  const registered = []
  const injected = []
  module.apply({
    slots: {
      inject(slot, callback) {
        injected.push(slot)
        callback()
        return () => {}
      },
      register(options, component) {
        registered.push({ options, component })
        return () => {}
      },
    },
  })

  assert.deepEqual(injected, ['shell.overlay'])
  assert.equal(registered.length, 1)
  assert.equal(registered[0].options.name, 'shell.overlay')
  assert.equal(registered[0].options.id, 'dsh-vidnote.window')
  assert.equal(typeof registered[0].component, 'function')
})
