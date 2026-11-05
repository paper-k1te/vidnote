import assert from 'node:assert/strict'
import { test } from 'node:test'
import { upstreamPath } from '../lib/proxy.js'

test('upstreamPath 还原成 vidnote 服务上的路径', () => {
  assert.equal(upstreamPath('/vidnote/app/api/health'), '/api/health')
  assert.equal(upstreamPath('/vidnote/app/api/frame?note=a&src=b'), '/api/frame?note=a&src=b')
  assert.equal(upstreamPath('/vidnote/app'), '/')
  assert.equal(upstreamPath('/vidnote/app/'), '/')
  assert.equal(upstreamPath(undefined), '/')
})

test('upstreamPath 不动别的路径', () => {
  assert.equal(upstreamPath('/api/health'), '/api/health')
})
