// vidnote 在 DSH 里的界面：注册成「对话 / 轨迹」旁边的第三个视图。
// 布局照着自己的窗口来——左侧导航（抓取 / 搜索）、顶栏、左边表单右边预览。
// 用 DSH 的主题变量，深浅色跟随；「打开原界面」交给宿主起独立窗口。
window.__ModuleLoader__.load({
  id: 'dsh-vidnote',
  factory(require) {
    const React = require('react')
    const h = React.createElement

    const NS = 'dsh-vidnote'
    const ACCENT = '#f97316'
    let localeFacade = null

    const TEXT = {
      zh: {
        brand: 'vidnote',
        viewLabel: 'B站笔记',
        fetchNav: '抓取视频',
        searchNav: '搜索',
        fetchTitle: '抓取视频',
        fetchSub: '把 B 站视频变成带时间戳的 Markdown 笔记',
        searchTitle: '搜索',
        searchSub: '先找视频，挑一条再回来抓',
        target: '链接或编号',
        targetHint: 'BV1xx411c7mD 或 https://www.bilibili.com/video/...',
        page: '分P',
        plan: '解析方案',
        planNone: '不转写（只抓字幕）',
        planVosk: 'Vosk 小模型（42 MB，快）',
        planTiny: 'whisper tiny',
        planBase: 'whisper base',
        planSmall: 'whisper small',
        go: '生成笔记',
        running: '正在抓取…',
        waiting: '已等待',
        seconds: '秒',
        preview: '预览',
        source: '源文',
        copy: '复制',
        copied: '已复制',
        download: '下载 .md',
        empty: '填入链接并点「生成笔记」，这里会显示渲染后的结果。',
        needsTarget: '请先填入 B 站链接或 BV 号。',
        keywordHint: '回车搜索，例如：Python 异步',
        search: '搜索',
        searching: '搜索中…',
        video: '视频',
        user: 'UP 主',
        emptySearch: '还没有搜索结果。',
        fillTarget: '点一条视频填入链接',
        legacy: '打开原界面',
        opened: '已打开窗口',
        fans: '粉丝',
        videos: '投稿',
        space: '空间',
        hostStale: '宿主里的插件还是旧版本：请重启 DSH 后再试。',
        noResult: '没有找到结果。',
      },
      en: {
        brand: 'vidnote',
        viewLabel: 'Bilibili Notes',
        fetchNav: 'Fetch video',
        searchNav: 'Search',
        fetchTitle: 'Fetch video',
        fetchSub: 'Turn a Bilibili video into timestamped Markdown',
        searchTitle: 'Search',
        searchSub: 'Find a video first, then come back to fetch it',
        target: 'Link or ID',
        targetHint: 'BV1xx411c7mD or https://www.bilibili.com/video/...',
        page: 'Part',
        plan: 'Transcription',
        planNone: 'Off (subtitles only)',
        planVosk: 'Vosk small (42 MB, fast)',
        planTiny: 'whisper tiny',
        planBase: 'whisper base',
        planSmall: 'whisper small',
        go: 'Generate note',
        running: 'Fetching…',
        waiting: 'elapsed',
        seconds: 's',
        preview: 'Preview',
        source: 'Source',
        copy: 'Copy',
        copied: 'Copied',
        download: 'Download .md',
        empty: 'Paste a link and press “Generate note”; the rendered note appears here.',
        needsTarget: 'Paste a Bilibili link or BV id first.',
        keywordHint: 'Press Enter to search, e.g. Python asyncio',
        search: 'Search',
        searching: 'Searching…',
        video: 'Videos',
        user: 'Uploaders',
        emptySearch: 'No results yet.',
        fillTarget: 'Click a video to fill the link',
        legacy: 'Open app window',
        opened: 'Window opened',
        fans: 'followers',
        videos: 'videos',
        space: 'Space',
        hostStale: 'The host still runs an older plugin. Restart DSH and try again.',
        noResult: 'Nothing found.',
      },
    }

    const FALLBACK_SNAPSHOT = { active: 'zh' }
    const FALLBACK_LOCALE = {
      subscribe: () => () => {},
      getSnapshot: () => FALLBACK_SNAPSHOT,
    }

    function useT() {
      const facade = localeFacade ?? FALLBACK_LOCALE
      const snapshot = React.useSyncExternalStore(
        facade.subscribe,
        facade.getSnapshot,
        facade.getSnapshot,
      )
      const active = String(snapshot?.active ?? 'zh').toLowerCase()
      return active.startsWith('en') ? TEXT.en : TEXT.zh
    }

    const STYLES = `
.vn-view { display: flex; height: 100%; min-height: 0; background: var(--dsw-alias-bg-base, #fff); color: var(--dsw-alias-label-primary, #18181b); font-size: 13px; }
.vn-side { width: 188px; flex: none; display: flex; flex-direction: column; gap: 2px; padding: 12px 10px; background: var(--dsw-specific-sidebar-fill, var(--dsw-alias-bg-layer-2, #f5f5f7)); border-right: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08)); }
.vn-brand { display: flex; align-items: center; gap: 8px; padding: 4px 8px 14px; }
.vn-logo { width: 22px; height: 22px; border-radius: 6px; background: ${ACCENT}; color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; }
.vn-brand b { font-size: 14px; font-weight: 600; letter-spacing: -.01em; }
.vn-nav { display: flex; align-items: center; gap: 9px; padding: 7px 9px; border: 0; border-radius: 6px; background: transparent; color: var(--dsw-alias-label-secondary, #52525b); font-size: 13px; text-align: left; cursor: pointer; }
.vn-nav:hover { background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.04)); color: var(--dsw-alias-label-primary, #18181b); }
.vn-nav[aria-current="true"] { background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.07)); color: var(--dsw-alias-label-primary, #18181b); font-weight: 500; }
.vn-nav svg { width: 15px; height: 15px; }
.vn-side-foot { margin-top: auto; display: flex; flex-direction: column; gap: 4px; }
.vn-side-foot .vn-ghost { width: 100%; justify-content: center; }
.vn-hint { padding: 4px 9px; color: var(--dsw-alias-label-secondary, #65656e); font-size: 11px; line-height: 1.5; }
.vn-main { flex: 1; min-width: 0; display: flex; flex-direction: column; min-height: 0; }
.vn-topbar { height: 52px; flex: none; display: flex; align-items: center; gap: 10px; padding: 0 20px; border-bottom: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08)); }
.vn-topbar h1 { margin: 0; font-size: 16px; font-weight: 600; letter-spacing: -.01em; }
.vn-topbar .vn-sub { color: var(--dsw-alias-label-secondary, #65656e); font-size: 12px; }
.vn-spacer { flex: 1; }
.vn-content { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(300px, 380px) minmax(0, 1fr); gap: 16px; padding: 16px 20px 20px; overflow: hidden; }
@media (max-width: 980px) { .vn-side { width: 60px; } .vn-brand b, .vn-nav span, .vn-hint, .vn-side-foot .vn-label { display: none; } .vn-content { grid-template-columns: 1fr; overflow: auto; } }
@media (max-width: 720px) { .vn-content { grid-template-columns: 1fr; overflow: auto; } .vn-topbar .vn-sub { display: none; } }
.vn-card { background: var(--dsw-alias-bg-layer-1, #fff); border: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08)); border-radius: 10px; display: flex; flex-direction: column; min-height: 0; box-shadow: 0 1px 2px rgba(16,24,40,.04); }
.vn-card-body { padding: 14px; }
.vn-preview-card { min-height: 0; }
.vn-preview-head { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-bottom: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08)); }
.vn-preview-head h2 { margin: 0; font-size: 13px; font-weight: 600; }
.vn-preview-scroll { flex: 1; min-height: 0; overflow: auto; padding: 12px 14px 20px; }
.vn-label { display: block; font-size: 12px; color: var(--dsw-alias-label-secondary, #52525b); margin: 0 0 6px; }
.vn-label:not(:first-child) { margin-top: 12px; }
.vn-input, .vn-select { width: 100%; box-sizing: border-box; height: 32px; padding: 0 10px; font-size: 13px; color: var(--dsw-alias-label-primary, #18181b); background: var(--dsw-alias-bg-base, #fff); border: 1px solid var(--dsw-alias-border-l2, rgba(0,0,0,.16)); border-radius: 6px; outline: none; }
.vn-input:focus, .vn-select:focus { border-color: ${ACCENT}; box-shadow: 0 0 0 3px rgba(249,115,21,.16); }
.vn-row { display: flex; gap: 10px; }
.vn-row > * { flex: 1; min-width: 0; }
.vn-actions { display: flex; align-items: center; gap: 10px; margin-top: 14px; }
.vn-primary { height: 32px; padding: 0 14px; border: 0; border-radius: 6px; font-size: 13px; font-weight: 600; color: #fff; background: ${ACCENT}; cursor: pointer; }
.vn-primary:hover:not(:disabled) { background: #ea620a; }
.vn-primary:disabled { opacity: .55; cursor: default; }
.vn-ghost { height: 28px; padding: 0 10px; border-radius: 6px; border: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.12)); background: transparent; color: var(--dsw-alias-label-secondary, #52525b); font-size: 12px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.vn-ghost:hover { color: var(--dsw-alias-label-primary, #18181b); border-color: var(--dsw-alias-border-l2, rgba(0,0,0,.2)); }
.vn-progress { display: flex; align-items: center; gap: 8px; flex: 1; font-size: 12px; color: var(--dsw-alias-label-secondary, #65656e); }
.vn-bar { position: relative; flex: 1; height: 4px; border-radius: 999px; overflow: hidden; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.08)); }
.vn-bar::after { content: ''; position: absolute; inset: 0; width: 38%; border-radius: 999px; background: ${ACCENT}; animation: vn-slide 1.15s ease-in-out infinite; }
@keyframes vn-slide { 0% { transform: translateX(-110%); } 100% { transform: translateX(310%); } }
.vn-error { color: var(--dsw-alias-state-error-primary, #b91c1c); font-size: 12px; white-space: pre-wrap; margin: 10px 0 0; }
.vn-empty { padding: 28px 8px; text-align: center; color: var(--dsw-alias-label-secondary, #777); font-size: 12px; }
.md-h { margin: 16px 0 6px; font-size: 15px; font-weight: 650; line-height: 1.4; }
.md-h:first-child { margin-top: 0; }
.md-p { margin: 6px 0; line-height: 1.7; font-size: 13px; }
.md-quote { margin: 8px 0; padding: 6px 10px; border-left: 3px solid ${ACCENT}; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.04)); border-radius: 0 6px 6px 0; }
.md-quote p { margin: 2px 0; font-size: 12.5px; line-height: 1.6; }
.md-list { margin: 6px 0; padding-left: 18px; }
.md-list li { margin: 2px 0; font-size: 13px; line-height: 1.65; }
.md-table-wrap { overflow-x: auto; margin: 8px 0; }
.md-table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
.md-table th, .md-table td { border: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.1)); padding: 4px 8px; text-align: left; vertical-align: top; }
.md-table th { background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.04)); font-weight: 600; }
.md-code { margin: 8px 0; padding: 8px 10px; border-radius: 6px; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.05)); font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px; overflow-x: auto; }
.md-hr { border: 0; border-top: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.1)); margin: 12px 0; }
.md-link { color: ${ACCENT}; text-decoration: none; }
.md-link:hover { text-decoration: underline; }
.md-code-inline { padding: 1px 4px; border-radius: 4px; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.06)); font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px; }
.vn-list { list-style: none; margin: 10px 0 0; padding: 0; overflow: auto; }
.vn-item { display: flex; flex-direction: column; gap: 3px; padding: 8px; border-radius: 7px; cursor: pointer; }
.vn-item:hover { background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.04)); }
.vn-item-title { font-size: 13px; line-height: 1.45; }
.vn-item-meta { font-size: 11.5px; color: var(--dsw-alias-label-secondary, #777); display: flex; flex-wrap: wrap; gap: 8px; }
.vn-item-meta a { color: ${ACCENT}; text-decoration: none; }
.vn-seg { display: inline-flex; gap: 2px; padding: 2px; border-radius: 6px; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.05)); }
.vn-seg button { border: 0; background: transparent; color: var(--dsw-alias-label-secondary, #52525b); font-size: 12px; padding: 3px 10px; border-radius: 5px; cursor: pointer; }
.vn-seg button[aria-pressed="true"] { background: var(--dsw-alias-bg-base, #fff); color: var(--dsw-alias-label-primary, #18181b); font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.12); }
`

    const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|\*[^*]+\*)/g

    /** 行内 Markdown → React 节点（只认粗体、斜体、代码、链接）。 */
    function inline(text) {
      const source = String(text ?? '')
      const nodes = []
      let last = 0
      let match
      INLINE.lastIndex = 0
      while ((match = INLINE.exec(source)) !== null) {
        if (match.index > last) nodes.push(source.slice(last, match.index))
        const token = match[0]
        const key = nodes.length
        if (token.startsWith('**')) nodes.push(h('strong', { key }, token.slice(2, -2)))
        else if (token.startsWith('`')) nodes.push(h('code', { key, className: 'md-code-inline' }, token.slice(1, -1)))
        else if (token.startsWith('[')) {
          const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token)
          nodes.push(link
            ? h('a', { key, className: 'md-link', href: link[2], target: '_blank', rel: 'noreferrer' }, link[1])
            : token)
        } else nodes.push(h('em', { key }, token.slice(1, -1)))
        last = match.index + token.length
      }
      if (last < source.length) nodes.push(source.slice(last))
      return nodes
    }

    function Block({ block }) {
      if (!block) return null
      switch (block.type) {
        case 'heading':
          return h(block.level <= 2 ? 'h2' : 'h3', { className: 'md-h' }, inline(block.text))
        case 'p':
          return h('p', { className: 'md-p' }, inline(block.text))
        case 'list':
          return h('ul', { className: 'md-list' }, block.items.map((item, index) => h('li', { key: index }, inline(item))))
        case 'quote':
          return h('blockquote', { className: 'md-quote' }, block.lines.map((line, index) => h('p', { key: index }, inline(line))))
        case 'table':
          return h('div', { className: 'md-table-wrap' },
            h('table', { className: 'md-table' },
              h('thead', null, h('tr', null, block.header.map((cell, index) => h('th', { key: index }, inline(cell))))),
              h('tbody', null, block.rows.map((row, rowIndex) => h('tr', { key: rowIndex },
                row.map((cell, cellIndex) => h('td', { key: cellIndex }, inline(cell))))))))
        case 'code':
          return h('pre', { className: 'md-code' }, block.text)
        case 'hr':
          return h('hr', { className: 'md-hr' })
        default:
          return null
      }
    }

    async function postJson(path, payload, t) {
      const response = await fetch(path, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
      })
      let body = null
      try {
        body = await response.json()
      } catch {
        body = null
      }
      if (response.status === 404 || response.status === 405) throw new Error(t.hostStale)
      if (!response.ok || body?.error) throw new Error(body?.error ?? `HTTP ${response.status}`)
      return body ?? {}
    }

    function copyText(text) {
      if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text)
      const area = document.createElement('textarea')
      area.value = text
      area.style.position = 'fixed'
      area.style.opacity = '0'
      document.body.appendChild(area)
      area.select()
      try {
        document.execCommand('copy')
      } finally {
        area.remove()
      }
      return Promise.resolve()
    }

    function downloadMarkdown(text) {
      const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      const first = text.match(/^title:\s*(.+)$/m)?.[1]
      anchor.href = url
      anchor.download = `${(first || 'vidnote').replace(/[\\/:*?"<>|]/g, '_').slice(0, 60)}.md`
      anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }

    function FetchView({ t, target, setTarget }) {
      const [page, setPage] = React.useState('1')
      const [plan, setPlan] = React.useState('none')
      const [status, setStatus] = React.useState('idle')
      const [markdown, setMarkdown] = React.useState('')
      const [blocks, setBlocks] = React.useState([])
      const [showSource, setShowSource] = React.useState(false)
      const [error, setError] = React.useState('')
      const [copied, setCopied] = React.useState(false)
      const [elapsed, setElapsed] = React.useState(0)

      React.useEffect(() => {
        if (status !== 'running') return undefined
        const started = Date.now()
        setElapsed(0)
        const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000)
        return () => clearInterval(timer)
      }, [status])

      const run = async () => {
        const value = target.trim()
        if (!value) {
          setError(t.needsTarget)
          return
        }
        setStatus('running')
        setError('')
        setCopied(false)
        try {
          const data = await postJson('/vidnote/api/fetch', {
            target: value,
            page: Number(page) || 1,
            transcribe: plan === 'none' ? '' : plan,
          }, t)
          setMarkdown(data.markdown ?? '')
          setBlocks(data.blocks ?? [])
          setStatus('done')
        } catch (failure) {
          setError(String(failure?.message ?? failure))
          setStatus('error')
        }
      }

      return h(React.Fragment, null,
        h('section', { className: 'vn-card' },
          h('div', { className: 'vn-card-body' },
            h('label', { className: 'vn-label', htmlFor: 'vn-target' }, t.target),
            h('input', {
              id: 'vn-target',
              className: 'vn-input',
              value: target,
              placeholder: t.targetHint,
              spellCheck: false,
              onChange: (event) => setTarget(event.target.value),
              onKeyDown: (event) => {
                if (event.key === 'Enter') run()
              },
            }),
            h('div', { className: 'vn-row' },
              h('div', null,
                h('label', { className: 'vn-label', htmlFor: 'vn-page' }, t.page),
                h('input', { id: 'vn-page', className: 'vn-input', type: 'number', min: 1, value: page, onChange: (event) => setPage(event.target.value) })),
              h('div', null,
                h('label', { className: 'vn-label', htmlFor: 'vn-plan' }, t.plan),
                h('select', { id: 'vn-plan', className: 'vn-select', value: plan, onChange: (event) => setPlan(event.target.value) },
                  h('option', { value: 'none' }, t.planNone),
                  h('option', { value: 'vosk-cn' }, t.planVosk),
                  h('option', { value: 'tiny' }, t.planTiny),
                  h('option', { value: 'base' }, t.planBase),
                  h('option', { value: 'small' }, t.planSmall)))),
            h('div', { className: 'vn-actions' },
              h('button', { className: 'vn-primary', disabled: status === 'running', onClick: run },
                status === 'running' ? t.running : t.go),
              status === 'running'
                ? h('div', { className: 'vn-progress' },
                    h('div', { className: 'vn-bar' }),
                    h('span', null, `${t.waiting} ${elapsed} ${t.seconds}`))
                : null),
            error ? h('p', { className: 'vn-error' }, error) : null)),

        h('section', { className: 'vn-card vn-preview-card' },
          h('div', { className: 'vn-preview-head' },
            h('h2', null, t.preview),
            h('span', { className: 'vn-spacer' }),
            blocks.length
              ? h('button', { className: 'vn-ghost', onClick: () => setShowSource(!showSource) },
                  showSource ? t.preview : t.source)
              : null,
            markdown
              ? h('button', {
                  className: 'vn-ghost',
                  onClick: () => {
                    copyText(markdown).then(() => {
                      setCopied(true)
                      setTimeout(() => setCopied(false), 1600)
                    })
                  },
                }, copied ? t.copied : t.copy)
              : null,
            markdown ? h('button', { className: 'vn-ghost', onClick: () => downloadMarkdown(markdown) }, t.download) : null),
          h('div', { className: 'vn-preview-scroll' },
            !blocks.length
              ? h('div', { className: 'vn-empty' }, t.empty)
              : showSource
                ? h('pre', { className: 'md-code', style: { margin: 0, whiteSpace: 'pre-wrap' } }, markdown)
                : blocks.map((block, index) => h(Block, { key: index, block })))))
    }

    function SearchView({ t, onPick }) {
      const [kind, setKind] = React.useState('video')
      const [keyword, setKeyword] = React.useState('')
      const [status, setStatus] = React.useState('idle')
      const [videos, setVideos] = React.useState([])
      const [users, setUsers] = React.useState([])
      const [error, setError] = React.useState('')

      const run = async () => {
        const word = keyword.trim()
        if (!word) return
        setStatus('searching')
        setError('')
        try {
          const data = await postJson('/vidnote/api/search', { keyword: word, type: kind, limit: 15 }, t)
          setVideos(data.videos ?? [])
          setUsers(data.users ?? [])
          setStatus('done')
        } catch (failure) {
          setError(String(failure?.message ?? failure))
          setStatus('error')
        }
      }

      const count = kind === 'video' ? videos.length : users.length

      return h('section', { className: 'vn-card', style: { gridColumn: '1 / -1' } },
        h('div', { className: 'vn-card-body', style: { display: 'flex', flexDirection: 'column', minHeight: 0 } },
          h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' } },
            h('div', { className: 'vn-seg' },
              h('button', { type: 'button', 'aria-pressed': kind === 'video', onClick: () => setKind('video') }, t.video),
              h('button', { type: 'button', 'aria-pressed': kind === 'user', onClick: () => setKind('user') }, t.user)),
            h('span', { className: 'vn-item-meta' }, t.fillTarget)),
          h('div', { className: 'vn-actions', style: { marginTop: 0 } },
            h('input', {
              className: 'vn-input',
              style: { flex: 1 },
              value: keyword,
              placeholder: t.keywordHint,
              spellCheck: false,
              onChange: (event) => setKeyword(event.target.value),
              onKeyDown: (event) => {
                if (event.key === 'Enter') run()
              },
            }),
            h('button', { className: 'vn-primary', disabled: status === 'searching', onClick: run },
              status === 'searching' ? t.searching : t.search)),
          error ? h('p', { className: 'vn-error' }, error) : null,
          h('ul', { className: 'vn-list' },
            kind === 'video'
              ? videos.map((video) => h('li', {
                  key: video.bvid,
                  className: 'vn-item',
                  onClick: () => onPick(video.url),
                },
                  h('div', { className: 'vn-item-title' }, video.title),
                  h('div', { className: 'vn-item-meta' },
                    h('span', null, video.author),
                    h('span', null, video.duration),
                    h('span', null, Number(video.play || 0).toLocaleString()))))
              : users.map((user) => h('li', { key: user.mid, className: 'vn-item' },
                  h('div', { className: 'vn-item-title' }, user.name),
                  h('div', { className: 'vn-item-meta' },
                    h('span', null, `${t.fans} ${Number(user.fans || 0).toLocaleString()}`),
                    h('span', null, `${t.videos} ${Number(user.videos || 0).toLocaleString()}`),
                    user.sign ? h('span', null, user.sign) : null,
                    h('a', { href: user.url, target: '_blank', rel: 'noreferrer' }, t.space)))),
            count === 0 ? h('li', { className: 'vn-empty' }, status === 'done' ? t.noResult : t.emptySearch) : null)))
    }

    function FetchIcon() {
      return h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true },
        h('path', { d: 'M12 3 20 9l-8 7-8-7 8-6Z' }),
        h('path', { d: 'M12 16v3' }))
    }

    function SearchIcon() {
      return h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true },
        h('circle', { cx: 11, cy: 11, r: 6 }),
        h('path', { d: 'm16 16 4.5 4.5' }))
    }

    function VidnoteView() {
      const t = useT()
      const [tab, setTab] = React.useState('fetch')
      const [target, setTarget] = React.useState('')
      const [opened, setOpened] = React.useState(false)

      const openWindow = async () => {
        try {
          const response = await fetch('/vidnote/window', { method: 'POST' })
          if (!response.ok) throw new Error(`HTTP ${response.status}`)
          setOpened(true)
          setTimeout(() => setOpened(false), 2000)
        } catch {
          setOpened(false)
        }
      }

      return h('div', { className: 'vn-view' },
        h('aside', { className: 'vn-side' },
          h('div', { className: 'vn-brand' },
            h('span', { className: 'vn-logo' }, 'V'),
            h('b', null, t.brand)),
          h('button', { type: 'button', className: 'vn-nav', 'aria-current': tab === 'fetch', onClick: () => setTab('fetch') },
            h(FetchIcon), h('span', null, t.fetchNav)),
          h('button', { type: 'button', className: 'vn-nav', 'aria-current': tab === 'search', onClick: () => setTab('search') },
            h(SearchIcon), h('span', null, t.searchNav)),
          h('div', { className: 'vn-side-foot' },
            h('button', { type: 'button', className: 'vn-ghost', onClick: openWindow }, opened ? t.opened : t.legacy))),
        h('main', { className: 'vn-main' },
          h('div', { className: 'vn-topbar' },
            h('h1', null, tab === 'fetch' ? t.fetchTitle : t.searchTitle),
            h('span', { className: 'vn-sub' }, tab === 'fetch' ? t.fetchSub : t.searchSub),
            h('span', { className: 'vn-spacer' })),
          h('div', { className: 'vn-content' },
            tab === 'fetch'
              ? h(FetchView, { t, target, setTarget })
              : h(SearchView, {
                  t,
                  onPick: (url) => {
                    setTarget(url)
                    setTab('fetch')
                  },
                }))))
    }

    return {
      inject: ['slots'],
      apply(ctx) {
        const locale = ctx.get('locale')
        localeFacade = locale
          ? {
              subscribe: (listener) => locale.subscribe(listener),
              getSnapshot: () => locale.getSnapshot(),
            }
          : null

        ctx.effect(() => {
          const style = document.createElement('style')
          style.textContent = STYLES
          document.head.appendChild(style)
          return () => style.remove()
        }, 'vidnote: styles')

        ctx.slots.inject('conversation.view', () =>
          ctx.slots.register(
            { name: 'conversation.view', id: 'vidnote', order: 20, label: () => TEXT.zh.viewLabel, locale: NS },
            VidnoteView,
          ))
      },
    }
  },
})
