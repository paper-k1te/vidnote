import { test } from 'node:test'
import assert from 'node:assert/strict'

import { guarded } from '../lib/admission.js'

function fakeResponse() {
  return {
    destroyed: false,
    writableEnded: false,
    status: 0,
    body: '',
    headers: {},
    writeHead(status, headers) {
      this.status = status
      this.headers = headers || {}
    },
    end(body) {
      this.writableEnded = true
      this.body = body ?? ''
    },
  }
}

test('rejects when connection is missing', async () => {
  const res = fakeResponse()
  let called = false
  await guarded(undefined, async () => { called = true })({}, res)
  assert.equal(called, false)
  assert.equal(res.status, 503)
})

test('rejects when requestRejection throws', async () => {
  const res = fakeResponse()
  await guarded({ requestRejection() { throw new Error('nope') } }, async () => {})({}, res)
  assert.equal(res.status, 503)
})

test('maps 401 and other rejections', async () => {
  const unauthorized = fakeResponse()
  await guarded({ requestRejection: () => 401 }, async () => {})({}, unauthorized)
  assert.equal(unauthorized.status, 401)

  const forbidden = fakeResponse()
  await guarded({ requestRejection: () => 403 }, async () => {})({}, forbidden)
  assert.equal(forbidden.status, 403)
})

test('admits an accepted request', async () => {
  const res = fakeResponse()
  let seen = null
  await guarded({ requestRejection: () => undefined }, async (req) => { seen = req })({ url: '/x' }, res)
  assert.deepEqual(seen, { url: '/x' })
  assert.equal(res.status, 0)
})
