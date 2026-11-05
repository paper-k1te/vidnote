import assert from 'node:assert/strict'
import { test } from 'node:test'
import { parseBlocks, parseInline, parseNote, stripFrontmatter } from '../lib/markdown.js'

test('stripFrontmatter 取标题并去掉头部', () => {
  const { meta, body } = stripFrontmatter('---\ntitle: 测试视频\nowner: 某UP\n---\n\n# 标题\n')
  assert.equal(meta.title, '测试视频')
  assert.equal(meta.owner, '某UP')
  assert.match(body, /^# 标题/)
})

test('parseInline 处理粗体、代码、链接', () => {
  assert.deepEqual(parseInline('看 **重点** 和 `code` 和 [链接](https://x.test)'), [
    { type: 'text', value: '看 ' },
    { type: 'strong', value: '重点' },
    { type: 'text', value: ' 和 ' },
    { type: 'code', value: 'code' },
    { type: 'text', value: ' 和 ' },
    { type: 'link', text: '链接', url: 'https://x.test' },
  ])
})

test('parseBlocks 解析标题、表格、引用、列表', () => {
  const blocks = parseBlocks([
    '## 视频信息',
    '',
    '| 项目 | 内容 |',
    '| --- | --- |',
    '| 链接 | https://b23.tv/x |',
    '',
    '> 没有字幕',
    '',
    '- 标签一',
    '- 标签二',
  ].join('\n'))

  assert.equal(blocks[0].type, 'heading')
  assert.equal(blocks[0].level, 2)
  assert.equal(blocks[1].type, 'table')
  assert.deepEqual(blocks[1].header, ['项目', '内容'])
  assert.deepEqual(blocks[1].rows, [['链接', 'https://b23.tv/x']])
  assert.equal(blocks[2].type, 'quote')
  assert.equal(blocks[3].type, 'list')
  assert.deepEqual(blocks[3].items, ['标签一', '标签二'])
})

test('parseBlocks 解析代码块与分隔线', () => {
  const blocks = parseBlocks('```js\nconsole.log(1)\n```\n\n---\n')
  assert.deepEqual(blocks[0], { type: 'code', lang: 'js', text: 'console.log(1)' })
  assert.equal(blocks[1].type, 'hr')
})

test('parseNote 组合 frontmatter 与正文', () => {
  const note = parseNote('---\ntitle: t\n---\n\n## 字幕\n\n**00:00** 你好\n')
  assert.equal(note.meta.title, 't')
  assert.equal(note.blocks[0].type, 'heading')
  assert.equal(note.blocks[1].type, 'p')
  assert.equal(note.blocks[1].text, '**00:00** 你好')
})
