import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { test } from 'node:test'
import { createHandlers } from '../lib/api.js'

function request(body) {
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

const okFetch = async (url) => ({
  ok: true,
  async json() {
    return {
      code: 0,
      data: { result: [{ result_type: 'video', data: [{ bvid: 'BV1', title: '标题', author: 'UP', duration: '1:00', play: 10 }] }] },
    }
  },
})

test('POST /vidnote/api/fetch 调命令行并返回 markdown', async () => {
  const calls = []
  const handlers = createHandlers({
    cliPath: 'vidnote',
    run: async (argv, options) => {
      calls.push({ argv, options })
      return '# note'
    },
  })
  const { req, res, state } = request()
  const done = handlers.fetch(req, res)
  sendBody(req, { target: 'BV1xx', page: 2, frames: 4, transcribe: 'vosk-cn' })
  await done

  assert.equal(state.status, 200)
  assert.deepEqual(state.json(), { markdown: '# note', target: 'BV1xx' })
  assert.deepEqual(calls[0].argv, ['fetch', 'BV1xx', '--stdout', '--page', '2', '--vosk'])
  assert.equal(calls[0].options.cliPath, 'vidnote')
})

test('POST /vidnote/api/fetch 缺 target 时 400', async () => {
  const handlers = createHandlers({ cliPath: 'vidnote', run: async () => '' })
  const { req, res, state } = request()
  const done = handlers.fetch(req, res)
  sendBody(req, {})
  await done
  assert.equal(state.status, 400)
  assert.match(state.json().error, /填入/)
})

test('POST /vidnote/api/fetch 命令行失败时 502 并带原因', async () => {
  const handlers = createHandlers({
    cliPath: 'vidnote',
    run: async () => {
      throw new Error('视频不存在')
    },
  })
  const { req, res, state } = request()
  const done = handlers.fetch(req, res)
  sendBody(req, { target: 'BV1' })
  await done
  assert.equal(state.status, 502)
  assert.match(state.json().error, /视频不存在/)
})

test('POST /vidnote/api/search 返回视频列表', async () => {
  const handlers = createHandlers({ cliPath: 'vidnote', fetchImpl: okFetch })
  const { req, res, state } = request()
  const done = handlers.search(req, res)
  sendBody(req, { keyword: 'python', type: 'video' })
  await done
  assert.equal(state.status, 200)
  assert.equal(state.json().videos[0].bvid, 'BV1')
})

test('POST /vidnote/api/search 空关键词 400', async () => {
  const handlers = createHandlers({ cliPath: 'vidnote', fetchImpl: okFetch })
  const { req, res, state } = request()
  const done = handlers.search(req, res)
  sendBody(req, { keyword: '   ' })
  await done
  assert.equal(state.status, 400)
})
