import assert from 'node:assert/strict'
import { test } from 'node:test'
import { parseUsers, parseVideos, searchUsers, searchVideos, userSearchUrl, videoSearchUrl } from '../lib/bili.js'

const data = {
  result: [
    {
      mid: 330127927,
      uname: '纸鸢菌゜',
      fans: 4986,
      videos: 35,
      usign: '<em class="keyword">纸鸢</em>菌゜的签名',
      official_verify: { desc: '知名 up 主' },
      upic: '//i0.hdslb.com/bfs/face/a.jpg',
    },
    { mid: 0, uname: '没有 mid 的脏数据' },
  ],
}

test('parseUsers 映射字段、去标签、补全头像协议', () => {
  assert.deepEqual(parseUsers(data), [
    {
      mid: 330127927,
      name: '纸鸢菌゜',
      fans: 4986,
      videos: 35,
      sign: '纸鸢菌゜的签名',
      verified: '知名 up 主',
      avatar: 'https://i0.hdslb.com/bfs/face/a.jpg',
      url: 'https://space.bilibili.com/330127927',
    },
  ])
})

test('parseUsers 按 limit 截断', () => {
  const many = { result: Array.from({ length: 5 }, (_, i) => ({ mid: i + 1, uname: `u${i}` })) }
  assert.equal(parseUsers(many, 2).length, 2)
})

test('userSearchUrl 带 bili_user 与编码后的关键词', () => {
  const url = userSearchUrl('纸鸢 菌')
  assert.match(url, /search_type=bili_user/)
  assert.match(url, /keyword=%E7%BA%B8%E9%B8%A2\+%E8%8F%8C/)
})

test('searchUsers 遇到风控 code 给出可读错误', async () => {
  const fetchImpl = async () => ({ ok: true, json: async () => ({ code: -352, message: '风控' }) })
  await assert.rejects(searchUsers('x', { fetchImpl }), /风控/)
})

test('searchUsers 返回解析后的列表', async () => {
  const fetchImpl = async () => ({ ok: true, json: async () => ({ code: 0, data }) })
  const users = await searchUsers('纸鸢菌', { fetchImpl })
  assert.equal(users.length, 1)
  assert.equal(users[0].name, '纸鸢菌゜')
})

test('searchUsers 空关键词直接报错', async () => {
  await assert.rejects(searchUsers('  ', {}), /不能为空/)
})

const grouped = {
  result: [
    { result_type: 'video', data: [
      { bvid: 'BV1', title: '<em>标题</em>', author: 'UP', duration: '3:20', play: 42 },
    ] },
    { result_type: 'bili_user', data: [{ mid: 1, uname: 'u' }] },
  ],
}

test('parseVideos 只取 video 分组并去标签', () => {
  assert.deepEqual(parseVideos(grouped), [
    { bvid: 'BV1', title: '标题', author: 'UP', duration: '3:20', play: 42, url: 'https://www.bilibili.com/video/BV1' },
  ])
})

test('videoSearchUrl 带编码后的关键词', () => {
  assert.match(videoSearchUrl('python 异步'), /keyword=python\+%E5%BC%82%E6%AD%A5/)
})

test('searchVideos 返回解析后的列表', async () => {
  const fetchImpl = async () => ({ ok: true, json: async () => ({ code: 0, data: grouped }) })
  const videos = await searchVideos('python', { fetchImpl })
  assert.equal(videos.length, 1)
  assert.equal(videos[0].bvid, 'BV1')
})
