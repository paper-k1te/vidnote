/**
 * 够用就好的 Markdown 解析：把 vidnote 生成的笔记拆成块，交给 React 渲染。
 *
 * 只覆盖笔记里实际出现的语法：frontmatter、标题、表格、引用、列表、代码块、
 * 分隔线和行内粗体/斜体/代码/链接。不追求通用，也不接收不可信 HTML。
 */

export function stripFrontmatter(markdown) {
  const text = String(markdown ?? '')
  const match = /^---\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/.exec(text)
  if (!match) return { meta: {}, body: text }
  const meta = {}
  for (const line of match[1].split(/\r?\n/)) {
    const pair = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(line)
    if (!pair) continue
    meta[pair[1]] = pair[2].replace(/^['"]|['"]$/g, '')
  }
  return { meta, body: text.slice(match[0].length).replace(/^\r?\n+/, '') }
}

/** 行内：**粗体**、*斜体*、`代码`、[文字](url)、![图](<路径>)。 */
export function parseInline(text) {
  const source = String(text ?? '')
  const nodes = []
  const pattern = /(!\[[^\]]*\]\(<[^>]+>\)|!\[[^\]]*\]\([^)]+\)|\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|\*[^*]+\*)/g
  let last = 0
  let match
  while ((match = pattern.exec(source)) !== null) {
    if (match.index > last) nodes.push({ type: 'text', value: source.slice(last, match.index) })
    const token = match[0]
    if (token.startsWith('!')) {
      const image = /^!\[([^\]]*)\]\(<?([^)>]+)>?\)$/.exec(token)
      nodes.push(image
        ? { type: 'image', alt: image[1], src: image[2] }
        : { type: 'text', value: token })
    } else if (token.startsWith('**')) nodes.push({ type: 'strong', value: token.slice(2, -2) })
    else if (token.startsWith('`')) nodes.push({ type: 'code', value: token.slice(1, -1) })
    else if (token.startsWith('[')) {
      const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token)
      nodes.push(link ? { type: 'link', text: link[1], url: link[2] } : { type: 'text', value: token })
    } else nodes.push({ type: 'em', value: token.slice(1, -1) })
    last = match.index + token.length
  }
  if (last < source.length) nodes.push({ type: 'text', value: source.slice(last) })
  return nodes
}

function splitRow(line) {
  return line
    .replace(/^\s*\|/, '')
    .replace(/\|\s*$/, '')
    .split('|')
    .map((cell) => cell.trim())
}

function isDivider(line) {
  return /^\s*\|?[\s:|-]+\|?\s*$/.test(line) && line.includes('-')
}

function isHr(line) {
  const text = line.trim()
  return /^([-*_])(?:\s*\1){2,}$/.test(text)
}

function isList(line) {
  return /^\s*[-*+]\s+/.test(line)
}

function startsBlock(line) {
  return (
    /^#{1,6}\s/.test(line) ||
    /^\s*>/.test(line) ||
    /^\s*\|/.test(line) ||
    isList(line) ||
    /^```/.test(line) ||
    isHr(line)
  )
}

export function parseBlocks(markdown) {
  const lines = String(markdown ?? '').split(/\r?\n/)
  const blocks = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]

    if (!line.trim()) {
      index += 1
      continue
    }

    const fence = /^```(\w*)\s*$/.exec(line)
    if (fence) {
      const code = []
      index += 1
      while (index < lines.length && !/^```\s*$/.test(lines[index])) {
        code.push(lines[index])
        index += 1
      }
      index += 1
      blocks.push({ type: 'code', lang: fence[1], text: code.join('\n') })
      continue
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    if (heading) {
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2].trim() })
      index += 1
      continue
    }

    if (isHr(line)) {
      blocks.push({ type: 'hr' })
      index += 1
      continue
    }

    if (/^\s*\|/.test(line) && index + 1 < lines.length && isDivider(lines[index + 1])) {
      const header = splitRow(line)
      index += 2
      const rows = []
      while (index < lines.length && /^\s*\|/.test(lines[index])) {
        rows.push(splitRow(lines[index]))
        index += 1
      }
      blocks.push({ type: 'table', header, rows })
      continue
    }

    if (/^\s*>/.test(line)) {
      const quote = []
      while (index < lines.length && /^\s*>/.test(lines[index])) {
        quote.push(lines[index].replace(/^\s*>\s?/, ''))
        index += 1
      }
      blocks.push({ type: 'quote', lines: quote })
      continue
    }

    if (isList(line)) {
      const items = []
      while (index < lines.length && isList(lines[index])) {
        items.push(lines[index].replace(/^\s*[-*+]\s+/, ''))
        index += 1
      }
      blocks.push({ type: 'list', items })
      continue
    }

    const paragraph = []
    while (index < lines.length && lines[index].trim() && !startsBlock(lines[index])) {
      paragraph.push(lines[index].trim())
      index += 1
    }
    if (paragraph.length) blocks.push({ type: 'p', text: paragraph.join(' ') })
    else index += 1
  }

  return blocks
}

export function parseNote(markdown) {
  const { meta, body } = stripFrontmatter(markdown)
  return { meta, blocks: parseBlocks(body) }
}
