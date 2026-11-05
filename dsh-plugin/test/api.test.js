import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { test } from 'node:test'
import { createHandlers } from '../lib/api.js'

function request() {
  const req = new EventEmitter()
  const res = new EventEmitter()
  const state = { status: 0, headers: null, body: '' }
  res.writeHead = (status, headers) => {
    state.status = status
    state.headers = headers
  }
  res.end = (text) => {
    state.body = text
    res.writableEnded = true
  }
  state.json = () => JSON.parse(state.body)
  return { req, res, state }
}

function sendBody(req, payload) {
  const text = payload === undefined ? '' : JSON.stringify(payload)
  setImmediate(() => {
    if (text) req.emit('data', Buffer.from(text, 'utf8'))
    req.emit('end')
  })
}

test('POST /vidnote/parse 把 Markdown 拆成块', async () => {
  const handlers = createHandlers()
  const { req, res, state } = request()
  const done = handlers.parse(req, res)
  sendBody(req, { markdown: '---\ntitle: t\n---\n\n## 标题\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n' })
  await done

  assert.equal(state.status, 200)
  const body = state.json()
  assert.equal(body.meta.title, 't')
  assert.equal(body.blocks[0].type, 'heading')
  assert.equal(body.blocks[1].type, 'table')
})

test('POST /vidnote/parse 空内容 400', async () => {
  const handlers = createHandlers()
  const { req, res, state } = request()
  const done = handlers.parse(req, res)
  sendBody(req, { markdown: '   ' })
  await done
  assert.equal(state.status, 400)
})
