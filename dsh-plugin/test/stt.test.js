import { test } from 'node:test'
import assert from 'node:assert/strict'

import { createSttServer } from '../lib/stt.js'

function readyService(transcript = { text: '你好，世界。', audioSeconds: 1.5 }) {
  let prepared = 0
  return {
    service: {
      snapshot: () => ({
        providers: [{ id: 'sensevoice-local', location: 'host-local', preparation: { phase: 'ready' } }],
        selection: { providerId: 'sensevoice-local' },
      }),
      prepare: () => { prepared += 1 },
      resolve: (request) => ({ ...request, provider: { id: 'sensevoice-local' } }),
      transcribe: async () => transcript,
    },
    preparedCount: () => prepared,
  }
}

test('transcribes a WAV body through speechToText', async () => {
  const { service } = readyService()
  const stt = createSttServer({ get: (key) => (key === 'speechToText' ? service : undefined) })
  await stt.ready
  try {
    const response = await fetch(stt.url, {
      method: 'POST',
      headers: { 'x-vidnote-token': stt.token, 'content-type': 'application/octet-stream' },
      body: new Uint8Array([82, 73, 70, 70]),
    })
    assert.equal(response.status, 200)
    const body = await response.json()
    assert.equal(body.text, '你好，世界。')
  } finally {
    await stt.stop()
  }
})

test('rejects a wrong token', async () => {
  const { service } = readyService()
  const stt = createSttServer({ get: () => service })
  await stt.ready
  try {
    const response = await fetch(stt.url, { method: 'POST', headers: { 'x-vidnote-token': 'nope' }, body: 'x' })
    assert.equal(response.status, 401)
  } finally {
    await stt.stop()
  }
})

test('reports when the voice bundle is not enabled', async () => {
  const stt = createSttServer({ get: () => undefined })
  await stt.ready
  try {
    const response = await fetch(stt.url, {
      method: 'POST',
      headers: { 'x-vidnote-token': stt.token },
      body: new Uint8Array([1]),
    })
    assert.equal(response.status, 503)
    const body = await response.json()
    assert.match(body.error, /speechToText/)
  } finally {
    await stt.stop()
  }
})

test('prepares an unprepared provider before transcribing', async () => {
  let phase = 'unprepared'
  const service = {
    snapshot: () => ({
      providers: [{ id: 'sensevoice-local', location: 'host-local', preparation: { phase } }],
      selection: { providerId: 'sensevoice-local' },
    }),
    prepare: () => { phase = 'ready' },
    resolve: (request) => ({ ...request }),
    transcribe: async () => ({ text: '准备好了', audioSeconds: 1 }),
  }
  const stt = createSttServer({ get: () => service }, { prepareTimeoutMs: 2000 })
  await stt.ready
  try {
    const response = await fetch(stt.url, {
      method: 'POST',
      headers: { 'x-vidnote-token': stt.token },
      body: new Uint8Array([1, 2, 3]),
    })
    assert.equal(response.status, 200)
    assert.equal((await response.json()).text, '准备好了')
  } finally {
    await stt.stop()
  }
})
