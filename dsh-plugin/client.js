// vidnote 的 DSH 原生界面：侧边栏一个「B站笔记」入口 + 主区域一整页，用 DSH 自己的
// 主题变量和布局，而不是把原来的窗口 iframe 进来。原窗口还留着「打开原界面」入口。
window.__ModuleLoader__.load({
  id: 'dsh-vidnote',
  factory(require) {
    const React = require('react')
    const h = React.createElement

    const PANEL = 'vidnote'
    const NS = 'dsh-vidnote'
    let localeFacade = null

    const TEXT = {
      zh: {
        title: 'B站笔记',
        subtitle: '把 B 站视频变成带时间戳的 Markdown',
        fetchTab: '抓取视频',
        searchTab: '搜索',
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
        result: '结果',
        copy: '复制 Markdown',
        copied: '已复制',
        download: '下载 .md',
        empty: '填入链接并点「生成笔记」，结果会显示在这里。',
        needsTarget: '请先填入 B 站链接或 BV 号。',
        keywordHint: '回车搜索，例如：Python 异步',
        search: '搜索',
        searching: '搜索中…',
        video: '视频',
        user: 'UP 主',
        emptySearch: '还没有搜索结果。',
        fillTarget: '点一条视频填入链接',
        legacy: '打开原界面',
        error: '出错了',
        fans: '粉丝',
        videos: '投稿',
        space: '空间',
      },
      en: {
        title: 'Bilibili Notes',
        subtitle: 'Turn a Bilibili video into timestamped Markdown',
        fetchTab: 'Fetch video',
        searchTab: 'Search',
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
        result: 'Result',
        copy: 'Copy Markdown',
        copied: 'Copied',
        download: 'Download .md',
        empty: 'Paste a link and press “Generate note”; the result appears here.',
        needsTarget: 'Paste a Bilibili link or BV id first.',
        keywordHint: 'Press Enter to search, e.g. Python asyncio',
        search: 'Search',
        searching: 'Searching…',
        video: 'Videos',
        user: 'Uploaders',
        emptySearch: 'No results yet.',
        fillTarget: 'Click a video to fill the link',
        legacy: 'Open original window',
        error: 'Something went wrong',
        fans: 'followers',
        videos: 'videos',
        space: 'Space',
      },
    }

    function useT() {
      const facade = localeFacade
      const snapshot = facade
        ? React.useSyncExternalStore(facade.subscribe, facade.getSnapshot, facade.getSnapshot)
        : null
      const active = String(snapshot?.active ?? 'zh').toLowerCase()
      return active.startsWith('en') ? TEXT.en : TEXT.zh
    }

    const STYLES = `
.vn-page { height: 100%; overflow: auto; color: var(--dsw-alias-label-primary, #111); }
.vn-inner { max-width: 980px; margin: 0 auto; padding: 28px 32px 64px; }
.vn-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 8px 0 18px; }
.vn-head h1 { font-size: 22px; font-weight: 650; letter-spacing: -0.01em; margin: 0; }
.vn-sub { margin: 6px 0 0; font-size: 13px; color: var(--dsw-alias-label-secondary, #666); }
.vn-tabs { display: inline-flex; gap: 2px; padding: 3px; border-radius: 9px; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.05)); margin-bottom: 18px; }
.vn-tab { border: 0; background: transparent; color: var(--dsw-alias-label-secondary, #555); font-size: 13px; padding: 6px 14px; border-radius: 7px; cursor: pointer; }
.vn-tab[aria-selected="true"] { background: var(--dsw-alias-bg-base, #fff); color: var(--dsw-alias-label-primary, #111); box-shadow: 0 1px 2px rgba(0,0,0,.12); font-weight: 600; }
.vn-card { border: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.1)); border-radius: 12px; background: var(--dsw-alias-bg-layer-1, #fff); padding: 18px; margin-bottom: 16px; }
.vn-label { display: block; font-size: 12px; color: var(--dsw-alias-label-secondary, #666); margin: 0 0 6px; }
.vn-input, .vn-select { width: 100%; box-sizing: border-box; height: 36px; padding: 0 10px; font-size: 13px; color: var(--dsw-alias-label-primary, #111); background: var(--dsw-alias-bg-base, #fff); border: 1px solid var(--dsw-alias-border-l2, rgba(0,0,0,.16)); border-radius: 8px; outline: none; }
.vn-input:focus, .vn-select:focus { border-color: var(--dsw-alias-brand-primary, #4d6bfe); box-shadow: 0 0 0 3px color-mix(in srgb, var(--dsw-alias-brand-primary, #4d6bfe) 18%, transparent); }
.vn-row { display: flex; gap: 12px; margin-top: 12px; }
.vn-row > * { flex: 1; min-width: 0; }
.vn-actions { display: flex; align-items: center; gap: 10px; margin-top: 16px; }
.vn-primary { height: 34px; padding: 0 16px; border: 0; border-radius: 8px; font-size: 13px; font-weight: 600; color: #fff; background: var(--dsw-alias-brand-primary, #4d6bfe); cursor: pointer; }
.vn-primary:disabled { opacity: .55; cursor: default; }
.vn-ghost { height: 32px; padding: 0 12px; border-radius: 8px; border: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.12)); background: transparent; color: var(--dsw-alias-label-secondary, #555); font-size: 12px; cursor: pointer; }
.vn-ghost:hover { color: var(--dsw-alias-label-primary, #111); border-color: var(--dsw-alias-border-l2, rgba(0,0,0,.2)); }
.vn-hint { font-size: 12px; color: var(--dsw-alias-label-secondary, #777); }
.vn-error { color: var(--dsw-alias-state-error-primary, #d33); font-size: 13px; white-space: pre-wrap; }
.vn-progress { display: flex; align-items: center; gap: 10px; flex: 1; font-size: 12px; color: var(--dsw-alias-label-secondary, #666); }
.vn-bar { position: relative; flex: 1; height: 4px; border-radius: 999px; overflow: hidden; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.08)); }
.vn-bar::after { content: ''; position: absolute; inset: 0; width: 38%; border-radius: 999px; background: var(--dsw-alias-brand-primary, #4d6bfe); animation: vn-slide 1.15s ease-in-out infinite; }
@keyframes vn-slide { 0% { transform: translateX(-110%); } 100% { transform: translateX(310%); } }
.vn-result-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.vn-result-head h2 { font-size: 13px; font-weight: 600; margin: 0; }
.vn-spacer { flex: 1; }
.vn-pre { margin: 0; max-height: min(58vh, 640px); overflow: auto; padding: 14px; border-radius: 9px; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.04)); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12.5px; line-height: 1.65; white-space: pre-wrap; word-break: break-word; tab-size: 2; }
.vn-empty { padding: 28px 8px; text-align: center; color: var(--dsw-alias-label-secondary, #777); font-size: 13px; list-style: none; }
.vn-seg { display: inline-flex; gap: 2px; padding: 3px; border-radius: 8px; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.05)); }
.vn-seg button { border: 0; background: transparent; color: var(--dsw-alias-label-secondary, #555); font-size: 12px; padding: 4px 12px; border-radius: 6px; cursor: pointer; }
.vn-seg button[aria-pressed="true"] { background: var(--dsw-alias-bg-base, #fff); color: var(--dsw-alias-label-primary, #111); font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.12); }
.vn-list { list-style: none; margin: 14px 0 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.vn-item { display: flex; flex-direction: column; gap: 4px; padding: 10px; border-radius: 8px; cursor: pointer; }
.vn-item:hover { background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.04)); }
.vn-item-title { font-size: 13px; line-height: 1.45; }
.vn-item-meta { font-size: 12px; color: var(--dsw-alias-label-secondary, #777); display: flex; flex-wrap: wrap; gap: 10px; }
.vn-item-meta a { color: var(--dsw-alias-brand-primary, #4d6bfe); text-decoration: none; }
`

    async function postJson(path, payload) {
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
      if (!response.ok || body?.error) {
        throw new Error(body?.error ?? `HTTP ${response.status}`)
      }
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

    function FetchTab({ t, target, setTarget }) {
      const [page, setPage] = React.useState('1')
      const [plan, setPlan] = React.useState('none')
      const [status, setStatus] = React.useState('idle')
      const [markdown, setMarkdown] = React.useState('')
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
          })
          setMarkdown(data.markdown ?? '')
          setStatus('done')
        } catch (failure) {
          setError(String(failure?.message ?? failure))
          setStatus('error')
        }
      }

      return h('div', null,
        h('section', { className: 'vn-card' },
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
          error ? h('p', { className: 'vn-error', style: { marginTop: '12px' } }, error) : null),

        h('section', { className: 'vn-card' },
          h('div', { className: 'vn-result-head' },
            h('h2', null, t.result),
            h('div', { className: 'vn-spacer' }),
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
          markdown
            ? h('pre', { className: 'vn-pre' }, markdown)
            : h('div', { className: 'vn-empty' }, t.empty)))
    }

    function SearchTab({ t, onPick }) {
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
          const data = await postJson('/vidnote/api/search', { keyword: word, type: kind, limit: 15 })
          setVideos(data.videos ?? [])
          setUsers(data.users ?? [])
          setStatus('done')
        } catch (failure) {
          setError(String(failure?.message ?? failure))
          setStatus('error')
        }
      }

      return h('section', { className: 'vn-card' },
        h('div', { style: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' } },
          h('div', { className: 'vn-seg' },
            h('button', { type: 'button', 'aria-pressed': kind === 'video', onClick: () => setKind('video') }, t.video),
            h('button', { type: 'button', 'aria-pressed': kind === 'user', onClick: () => setKind('user') }, t.user)),
          h('div', { className: 'vn-hint' }, t.fillTarget)),
        h('div', { style: { display: 'flex', gap: '10px' } },
          h('input', {
            className: 'vn-input',
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
        error ? h('p', { className: 'vn-error', style: { marginTop: '12px' } }, error) : null,
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
                  h('span', null, `${Number(video.play || 0).toLocaleString()} 播放`))))
            : users.map((user) => h('li', { key: user.mid, className: 'vn-item' },
                h('div', { className: 'vn-item-title' }, user.name),
                h('div', { className: 'vn-item-meta' },
                  h('span', null, `${t.fans} ${Number(user.fans || 0).toLocaleString()}`),
                  h('span', null, `${t.videos} ${Number(user.videos || 0).toLocaleString()}`),
                  user.sign ? h('span', null, user.sign) : null,
                  h('a', { href: user.url, target: '_blank', rel: 'noreferrer' }, t.space)))),
          (kind === 'video' ? videos.length : users.length) === 0
            ? h('li', { className: 'vn-empty' }, t.emptySearch)
            : null))
    }

    function Page() {
      const t = useT()
      const [tab, setTab] = React.useState('fetch')
      const [target, setTarget] = React.useState('')

      const openLegacy = async () => {
        try {
          const response = await fetch('/vidnote/url', { headers: { accept: 'application/json' } })
          const body = await response.json()
          if (body?.url) window.open(body.url, '_blank', 'noopener')
        } catch {
          // 服务没起来时静默：原生界面本身还能用
        }
      }

      return h('div', { className: 'vn-page' },
        h('div', { className: 'vn-inner' },
          h('header', { className: 'vn-head', 'data-window-drag': true },
            h('div', null,
              h('h1', null, t.title),
              h('p', { className: 'vn-sub' }, t.subtitle)),
            h('button', { className: 'vn-ghost', onClick: openLegacy }, t.legacy)),
          h('div', { className: 'vn-tabs', role: 'tablist' },
            h('button', { className: 'vn-tab', role: 'tab', 'aria-selected': tab === 'fetch', onClick: () => setTab('fetch') }, t.fetchTab),
            h('button', { className: 'vn-tab', role: 'tab', 'aria-selected': tab === 'search', onClick: () => setTab('search') }, t.searchTab)),
          tab === 'fetch'
            ? h(FetchTab, { t, target, setTarget })
            : h(SearchTab, {
                t,
                onPick: (url) => {
                  setTarget(url)
                  setTab('fetch')
                },
              })))
    }

    function KiteIcon({ size = 16 }) {
      return h('svg', {
        width: size,
        height: size,
        viewBox: '0 0 24 24',
        fill: 'none',
        stroke: 'currentColor',
        strokeWidth: 1.7,
        strokeLinecap: 'round',
        strokeLinejoin: 'round',
        'aria-hidden': true,
      },
        h('path', { d: 'M12 3 20 9l-8 7-8-7 8-6Z' }),
        h('path', { d: 'M12 16v3' }),
        h('path', { d: 'M12 19c-1.6 0-2.6.9-3 2.2 1.6.4 2.7-.2 3-2.2Z' }))
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

        ctx.slots.inject('main', () =>
          ctx.slots.register({ name: 'main', key: PANEL, locale: NS }, Page))
        ctx.slots.inject('sidebar.panellist', () =>
          ctx.slots.register(
            { name: 'sidebar.panellist', id: PANEL, order: 2, label: () => TEXT.zh.title, locale: NS },
            KiteIcon,
          ))
      },
    }
  },
})
