import assert from 'node:assert/strict'
import { test } from 'node:test'

/** 假的 React / DSH 运行时，只验证客户端模块的注册接线（不渲染）。 */
test('client.js 注册主面板与侧边栏入口', async () => {
  let captured
  const styleNode = { textContent: '', remove() {} }
  globalThis.document = {
    head: { appendChild() {} },
    createElement: () => styleNode,
  }
  globalThis.window = {
    __ModuleLoader__: {
      load(definition) {
        captured = definition
      },
    },
  }

  await import('../client.js')
  assert.equal(captured.id, 'dsh-vidnote')

  const React = {
    createElement: (...args) => args,
    Fragment: Symbol('Fragment'),
    useState: (value) => [value, () => {}],
    useEffect: () => {},
    useSyncExternalStore: (_subscribe, getSnapshot) => getSnapshot(),
  }
  const module = captured.factory((name) => {
    if (name === 'react') return React
    if (name === 'react-dom') return {}
    throw new Error(`unexpected module: ${name}`)
  })

  const injections = []
  const registered = []
  const effects = []
  const ctx = {
    get: () => undefined,
    effect(fn) {
      effects.push(fn())
      return () => {}
    },
    slots: {
      inject(slot, callback) {
        injections.push(slot)
        callback()
        return () => {}
      },
      register(options, component) {
        registered.push({ options, component })
        return () => {}
      },
    },
  }

  module.apply(ctx)

  assert.deepEqual(injections, ['conversation.view'])
  assert.equal(registered.length, 1)
  assert.equal(registered[0].options.name, 'conversation.view')
  assert.equal(registered[0].options.id, 'vidnote')
  assert.equal(registered[0].options.order, 20)
  assert.equal(typeof registered[0].component, 'function')
  assert.equal(effects.length, 1)
})
