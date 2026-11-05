// vidnote 在 DSH 里的界面：注册成「对话 / 轨迹」旁边的第三个视图。
// 布局照着自己的窗口来——左侧导航（抓取 / 搜索 / 登录 / 下载）、顶栏、左边表单右边预览。
// 抓取/进度/关键帧/选目录/依赖安装都通过 /vidnote/app/api/* 代理给 vidnote 自己的 serve-ui。
// 状态放在模块级 store 里，切到「对话」再切回来不会丢。
window.__ModuleLoader__.load({
  id: 'dsh-vidnote',
  factory(require) {
    const React = require('react')
    const h = React.createElement

    const NS = 'dsh-vidnote'
    const ACCENT = '#f97316'
    const API = '/vidnote/app/api'
    let localeFacade = null

    const TEXT = {
      zh: {
        brand: 'vidnote',
        viewLabel: 'B站笔记',
        fetchNav: '抓取视频',
        searchNav: '搜索',
        loginNav: '登录 B 站',
        downloadNav: '下载',
        fetchTitle: '抓取视频',
        fetchSub: '把 B 站视频变成带时间戳的 Markdown 笔记',
        searchTitle: '搜索',
        searchSub: '先找视频，挑一条再回来抓',
        loginTitle: '登录 B 站',
        loginSub: '可选，只用于读取登录后才可见的字幕',
        downloadTitle: '下载',
        downloadSub: 'whisper 依赖与模型下载渠道',
        target: '链接或编号',
        targetHint: 'BV1xx411c7mD 或 https://www.bilibili.com/video/...',
        page: '分P',
        frames: '关键帧',
        outdir: '输出目录',
        outdirHint: '留空 = 当前目录',
        pick: '选择',
        plan: '解析方案',
        planNone: '不转写 · 只输出元数据',
        planVosk: 'Vosk 小模型 · 快、占用小、自动分句',
        planTiny: 'whisper tiny · 最快，质量一般',
        planBase: 'whisper base · 速度与质量平衡',
        planSmall: 'whisper small · 中文质量最好',
        planHint: 'whisper 的依赖安装和模型下载渠道在左侧「下载」页。',
        go: '生成笔记',
        running: '正在抓取…',
        preparing: '准备中…',
        preview: '预览',
        source: '源文',
        copy: '复制',
        copied: '已复制',
        download: '下载 .md',
        openFile: '打开文件',
        openFolder: '打开文件夹',
        empty: '填入链接并点「生成笔记」，这里会显示渲染后的结果。',
        needsTarget: '请先填入 B 站链接或 BV 号。',
        warning: '提示',
        keywordHint: '输入关键词后回车，例如：Python 异步',
        search: '搜索',
        searching: '搜索中…',
        video: '视频',
        user: '作者',
        emptySearch: '还没有搜索结果。',
        fillTarget: '点击视频填入编号',
        fans: '粉丝',
        videos: '投稿',
        space: '空间',
        cookie: 'Cookie',
        cookieHint: '大部分字幕需要登录态。粘贴 SESSDATA=... 或整段 Cookie；只用于本次抓取，不写进笔记，也不保存。',
        cookiePlaceholder: 'SESSDATA=...',
        channel: '下载渠道',
        channelAuto: '自动（完整版内置优先）',
        channelOfficial: 'HuggingFace 官方',
        channelMirror: 'hf-mirror 国内镜像',
        channelHint: 'whisper 模型第一次使用时按这里的渠道下载；Vosk 模型完整版已内置。',
        depsTitle: 'whisper 依赖',
        depsChecking: '正在检查…',
        depsInstalled: '已安装，可以直接选 whisper。',
        depsMissing: '还没有安装 whisper 依赖，装好后才能选 whisper。',
        depsInstall: '安装 whisper 依赖',
        depsInstalling: '正在安装…',
        legacy: '打开原界面',
        opened: '已打开窗口',
        hostStale: '宿主里的插件还是旧版本：请重启 DSH 后再试。',
        noResult: '没有找到结果。',
        error: '出错了',
      },
      en: {
        brand: 'vidnote',
        viewLabel: 'Bilibili Notes',
        fetchNav: 'Fetch',
        searchNav: 'Search',
        loginNav: 'Sign in',
        downloadNav: 'Downloads',
        fetchTitle: 'Fetch video',
        fetchSub: 'Turn a Bilibili video into timestamped Markdown',
        searchTitle: 'Search',
        searchSub: 'Find a video first, then come back to fetch it',
        loginTitle: 'Sign in to Bilibili',
        loginSub: 'Optional, only for subtitles that require a login',
        downloadTitle: 'Downloads',
        downloadSub: 'whisper dependencies and model download channel',
        target: 'Link or ID',
        targetHint: 'BV1xx411c7mD or https://www.bilibili.com/video/...',
        page: 'Part',
        frames: 'Keyframes',
        outdir: 'Output folder',
        outdirHint: 'Empty = current directory',
        pick: 'Choose',
        plan: 'Transcription',
        planNone: 'Off · metadata only',
        planVosk: 'Vosk small · fast and small',
        planTiny: 'whisper tiny · fastest, rough',
        planBase: 'whisper base · balanced',
        planSmall: 'whisper small · best Chinese',
        planHint: 'whisper dependencies and download channel live on the Downloads page.',
        go: 'Generate note',
        running: 'Fetching…',
        preparing: 'Preparing…',
        preview: 'Preview',
        source: 'Source',
        copy: 'Copy',
        copied: 'Copied',
        download: 'Download .md',
        openFile: 'Open file',
        openFolder: 'Open folder',
        empty: 'Paste a link and press “Generate note”; the rendered note appears here.',
        needsTarget: 'Paste a Bilibili link or BV id first.',
        warning: 'Note',
        keywordHint: 'Enter a keyword and press Enter',
        search: 'Search',
        searching: 'Searching…',
        video: 'Videos',
        user: 'Uploaders',
        emptySearch: 'No results yet.',
        fillTarget: 'Click a video to fill the id',
        fans: 'followers',
        videos: 'videos',
        space: 'Space',
        cookie: 'Cookie',
        cookieHint: 'Most subtitles need a login. Paste SESSDATA=... or the whole cookie; it is used for this fetch only and never stored.',
        cookiePlaceholder: 'SESSDATA=...',
        channel: 'Download channel',
        channelAuto: 'Auto (bundled first)',
        channelOfficial: 'HuggingFace',
        channelMirror: 'hf-mirror',
        channelHint: 'The first whisper run downloads the model from this channel; Vosk is bundled in the full build.',
        depsTitle: 'whisper dependencies',
        depsChecking: 'Checking…',
        depsInstalled: 'Installed; whisper is ready.',
        depsMissing: 'whisper dependencies are not installed yet.',
        depsInstall: 'Install whisper dependencies',
        depsInstalling: 'Installing…',
        legacy: 'Open app window',
        opened: 'Window opened',
        hostStale: 'The host still runs an older plugin. Restart DSH and try again.',
        noResult: 'Nothing found.',
        error: 'Something went wrong',
      },
    }

    const FALLBACK_SNAPSHOT = { active: 'zh' }
    const FALLBACK_LOCALE = {
      subscribe: () => () => {},
      getSnapshot: () => FALLBACK_SNAPSHOT,
    }

    function currentText() {
      const snapshot = localeFacade?.getSnapshot?.()
      const active = String(snapshot?.active ?? 'zh').toLowerCase()
      return active.startsWith('en') ? TEXT.en : TEXT.zh
    }

    function useT() {
      const facade = localeFacade ?? FALLBACK_LOCALE
      const snapshot = React.useSyncExternalStore(
        facade.subscribe,
        facade.getSnapshot,
        facade.getSnapshot,
      )
      return String(snapshot?.active ?? 'zh').toLowerCase().startsWith('en') ? TEXT.en : TEXT.zh
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
.vn-nav svg { width: 15px; height: 15px; flex: none; }
.vn-side-foot { margin-top: auto; display: flex; flex-direction: column; gap: 4px; }
.vn-side-foot .vn-ghost { width: 100%; justify-content: center; }
.vn-main { flex: 1; min-width: 0; display: flex; flex-direction: column; min-height: 0; }
.vn-topbar { height: 52px; flex: none; display: flex; align-items: center; gap: 10px; padding: 0 20px; border-bottom: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08)); }
.vn-topbar h1 { margin: 0; font-size: 16px; font-weight: 600; letter-spacing: -.01em; }
.vn-topbar .vn-sub { color: var(--dsw-alias-label-secondary, #65656e); font-size: 12px; }
.vn-spacer { flex: 1; }
.vn-content { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(300px, 380px) minmax(0, 1fr); gap: 16px; padding: 16px 20px 20px; overflow: hidden; }
.vn-content-single { flex: 1; min-height: 0; display: flex; flex-direction: column; gap: 16px; padding: 16px 20px 20px; overflow: auto; }
@media (max-width: 980px) { .vn-side { width: 60px; } .vn-brand b, .vn-nav span, .vn-side-foot .vn-ghost span { display: none; } .vn-content { grid-template-columns: 1fr; overflow: auto; } }
.vn-card { background: var(--dsw-alias-bg-layer-1, #fff); border: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08)); border-radius: 10px; display: flex; flex-direction: column; min-height: 0; box-shadow: 0 1px 2px rgba(16,24,40,.04); }
.vn-card-body { padding: 14px; }
.vn-preview-head { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-bottom: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08)); flex-wrap: wrap; }
.vn-preview-head h2 { margin: 0; font-size: 13px; font-weight: 600; }
.vn-preview-scroll { flex: 1; min-height: 0; overflow: auto; padding: 12px 14px 20px; }
.vn-label { display: block; font-size: 12px; color: var(--dsw-alias-label-secondary, #52525b); margin: 0 0 6px; }
.vn-label:not(:first-child) { margin-top: 12px; }
.vn-input, .vn-select { width: 100%; box-sizing: border-box; height: 32px; padding: 0 10px; font-size: 13px; color: var(--dsw-alias-label-primary, #18181b); background: var(--dsw-alias-bg-base, #fff); border: 1px solid var(--dsw-alias-border-l2, rgba(0,0,0,.16)); border-radius: 6px; outline: none; }
.vn-input:focus, .vn-select:focus { border-color: ${ACCENT}; box-shadow: 0 0 0 3px rgba(249,115,21,.16); }
.vn-row { display: flex; gap: 10px; }
.vn-row > * { flex: 1; min-width: 0; }
.vn-outdir { display: flex; gap: 8px; }
.vn-outdir .vn-input { flex: 1; }
.vn-hint { font-size: 11px; color: var(--dsw-alias-label-secondary, #65656e); line-height: 1.55; margin: 6px 0 0; }
.vn-actions { display: flex; align-items: center; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
.vn-primary { height: 32px; padding: 0 14px; border: 0; border-radius: 6px; font-size: 13px; font-weight: 600; color: #fff; background: ${ACCENT}; cursor: pointer; }
.vn-primary:hover:not(:disabled) { background: #ea620a; }
.vn-primary:disabled { opacity: .55; cursor: default; }
.vn-ghost { height: 28px; padding: 0 10px; border-radius: 6px; border: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.12)); background: transparent; color: var(--dsw-alias-label-secondary, #52525b); font-size: 12px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.vn-ghost:hover { color: var(--dsw-alias-label-primary, #18181b); border-color: var(--dsw-alias-border-l2, rgba(0,0,0,.2)); }
.vn-progress { margin-top: 12px; }
.vn-progress-label { display: flex; justify-content: space-between; font-size: 12px; color: var(--dsw-alias-label-secondary, #65656e); margin-bottom: 6px; gap: 10px; }
.vn-bar { position: relative; height: 5px; border-radius: 999px; overflow: hidden; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.08)); }
.vn-bar i { display: block; height: 100%; border-radius: 999px; background: ${ACCENT}; transition: width .25s ease; }
.vn-bar.indeterminate i { width: 38%; animation: vn-slide 1.15s ease-in-out infinite; }
@keyframes vn-slide { 0% { transform: translateX(-110%); } 100% { transform: translateX(310%); } }
.vn-error { color: var(--dsw-alias-state-error-primary, #b91c1c); font-size: 12px; white-space: pre-wrap; margin: 10px 0 0; }
.vn-warning { color: var(--dsw-alias-state-warn-primary, #b45309); font-size: 12px; margin: 8px 0 0; }
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
.md-img { display: block; max-width: 100%; margin: 8px 0; border-radius: 6px; border: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08)); }
.vn-list { list-style: none; margin: 10px 0 0; padding: 0; overflow: auto; }
.vn-item { display: flex; flex-direction: column; gap: 3px; padding: 8px; border-radius: 7px; cursor: pointer; }
.vn-item:hover { background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.04)); }
.vn-item-title { font-size: 13px; line-height: 1.45; }
.vn-item-meta { font-size: 11.5px; color: var(--dsw-alias-label-secondary, #777); display: flex; flex-wrap: wrap; gap: 8px; }
.vn-item-meta a { color: ${ACCENT}; text-decoration: none; }
.vn-seg { display: inline-flex; gap: 2px; padding: 2px; border-radius: 6px; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.05)); }
.vn-seg button { border: 0; background: transparent; color: var(--dsw-alias-label-secondary, #52525b); font-size: 12px; padding: 3px 10px; border-radius: 5px; cursor: pointer; }
.vn-seg button[aria-pressed="true"] { background: var(--dsw-alias-bg-base, #fff); color: var(--dsw-alias-label-primary, #18181b); font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.12); }
.vn-deps-state { font-size: 12px; color: var(--dsw-alias-label-secondary, #52525b); line-height: 1.6; margin: 6px 0 0; }
`

    // ---------------- 会话内持久化的状态 ----------------
    const DEFAULTS = {
      tab: 'fetch',
      target: '',
      page: '1',
      frames: '6',
      outdir: '',
      plan: '',
      cookie: '',
      channel: 'auto',
      status: 'idle',
      jobId: '',
      phase: '',
      done: 0,
      total: 0,
      note: '',
      blocks: [],
      notePath: '',
      warning: '',
      error: '',
      searchKind: 'video',
      keyword: '',
      searchStatus: 'idle',
      results: [],
      searchError: '',
      health: null,
      deps: null,
      depsBusy: false,
      opened: false,
    }
    let state = { ...DEFAULTS }
    const listeners = new Set()

    function set(patch) {
      state = { ...state, ...patch }
      for (const listener of listeners) listener()
    }

    function subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    }

    function useStore() {
      return React.useSyncExternalStore(subscribe, () => state, () => state)
    }

    async function call(path, { method = 'GET', body } = {}) {
      const response = await fetch(`${API}${path}`, {
        method,
        headers: body ? { 'content-type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      })
      let data = null
      try {
        data = await response.json()
      } catch {
        data = null
      }
      if (response.status === 404 || response.status === 405) throw new Error(currentText().hostStale)
      if (!response.ok) throw new Error(data?.error ?? `HTTP ${response.status}`)
      return data ?? {}
    }

    let jobTimer = null

    function stopJobPolling() {
      if (jobTimer) {
        clearInterval(jobTimer)
        jobTimer = null
      }
    }

    function pollJob(jobId) {
      if (jobTimer && state.jobId === jobId) return
      stopJobPolling()
      jobTimer = setInterval(async () => {
        try {
          const job = await call(`/job?id=${encodeURIComponent(jobId)}`)
          if (job.error && !job.status) {
            stopJobPolling()
            set({ status: 'error', error: String(job.error) })
            return
          }
          set({ phase: job.phase ?? '', done: Number(job.done ?? 0), total: Number(job.total ?? 0) })
          if (job.status === 'done') {
            stopJobPolling()
            const result = job.result ?? {}
            let blocks = []
            try {
              const parsed = await fetch('/vidnote/parse', {
                method: 'POST',
                headers: { 'content-type': 'application/json' },
                body: JSON.stringify({ markdown: result.note ?? '' }),
              }).then((response) => response.json())
              blocks = parsed.blocks ?? []
            } catch {
              blocks = []
            }
            set({
              status: 'done',
              note: result.note ?? '',
              blocks,
              notePath: result.path ?? '',
              warning: result.warning ?? '',
              phase: job.phase ?? '',
            })
          } else if (job.status === 'error') {
            stopJobPolling()
            set({ status: 'error', error: job.error ?? currentText().error })
          }
        } catch (failure) {
          stopJobPolling()
          set({ status: 'error', error: String(failure?.message ?? failure) })
        }
      }, 700)
    }

    async function startFetch() {
      const target = state.target.trim()
      if (!target) {
        set({ error: currentText().needsTarget })
        return
      }
      set({
        status: 'running', phase: currentText().preparing, done: 0, total: 0,
        error: '', warning: '', note: '', blocks: [], notePath: '', jobId: '',
      })
      try {
        const data = await call('/fetch', {
          method: 'POST',
          body: {
            target,
            page: Number(state.page) || 1,
            frames: Number(state.frames) || 0,
            outdir: state.outdir.trim(),
            cookie: state.cookie.trim(),
            channel: state.channel,
            transcribe: state.plan !== '',
            model: state.plan,
          },
        })
        if (data.error) throw new Error(data.error)
        set({ jobId: data.job })
        pollJob(data.job)
      } catch (failure) {
        set({ status: 'error', error: String(failure?.message ?? failure) })
      }
    }

    async function runSearch() {
      const keyword = state.keyword.trim()
      if (!keyword) return
      set({ searchStatus: 'searching', searchError: '' })
      try {
        const data = await call(`/search?q=${encodeURIComponent(keyword)}&type=${state.searchKind}&limit=15`)
        if (data.error) throw new Error(data.error)
        set({ results: data.results ?? [], searchStatus: 'done' })
      } catch (failure) {
        set({ searchStatus: 'error', searchError: String(failure?.message ?? failure) })
      }
    }

    async function loadHealth() {
      try {
        const health = await call('/health')
        set({ health, deps: health.whisper_deps ?? null })
      } catch {
        // 服务没起来时等用户操作再触发
      }
    }

    async function installDeps() {
      set({ depsBusy: true, deps: { ...(state.deps ?? {}), running: true, phase: currentText().preparing } })
      try {
        const deps = await call('/deps/install', { method: 'POST', body: {} })
        set({ deps })
        pollDeps()
      } catch (failure) {
        set({ depsBusy: false, deps: { ...(state.deps ?? {}), running: false, last_error: String(failure?.message ?? failure) } })
      }
    }

    let depsTimer = null

    function pollDeps() {
      if (depsTimer) return
      depsTimer = setInterval(async () => {
        try {
          const deps = await call('/deps')
          set({ deps })
          if (!deps.running) {
            clearInterval(depsTimer)
            depsTimer = null
            set({ depsBusy: false })
          }
        } catch {
          clearInterval(depsTimer)
          depsTimer = null
          set({ depsBusy: false })
        }
      }, 800)
    }

    async function pickFolder() {
      try {
        const data = await call('/pick-folder', { method: 'POST', body: {} })
        if (data.path) set({ outdir: data.path })
      } catch {
        // 用户取消或系统不支持时什么都不做
      }
    }

    async function reveal(path, folder) {
      if (!path) return
      try {
        await call(folder ? '/reveal-folder' : '/reveal', { method: 'POST', body: { path } })
      } catch {
        // 打开失败不打断界面
      }
    }

    async function openWindow() {
      try {
        const response = await fetch('/vidnote/window', { method: 'POST' })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        set({ opened: true })
        setTimeout(() => set({ opened: false }), 2000)
      } catch {
        set({ opened: false })
      }
    }

    // ---------------- Markdown 渲染 ----------------
    const INLINE = /(!\[[^\]]*\]\(<[^>]+>\)|!\[[^\]]*\]\([^)]+\)|\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|\*[^*]+\*)/g

    function inline(text, notePath) {
      const source = String(text ?? '')
      const nodes = []
      let last = 0
      let match
      INLINE.lastIndex = 0
      while ((match = INLINE.exec(source)) !== null) {
        if (match.index > last) nodes.push(source.slice(last, match.index))
        const token = match[0]
        const key = nodes.length
        if (token.startsWith('!')) {
          const image = /^!\[([^\]]*)\]\(<?([^)>]+)>?\)$/.exec(token)
          if (image && notePath) {
            const src = `${API}/frame?note=${encodeURIComponent(notePath)}&src=${encodeURIComponent(image[2])}`
            nodes.push(h('img', { key, className: 'md-img', src, alt: image[1], loading: 'lazy' }))
          } else if (image) {
            nodes.push(h('span', { key, className: 'md-code-inline' }, image[1] || 'image'))
          } else nodes.push(token)
        } else if (token.startsWith('**')) nodes.push(h('strong', { key }, token.slice(2, -2)))
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

    function Block({ block, notePath }) {
      if (!block) return null
      switch (block.type) {
        case 'heading':
          return h(block.level <= 2 ? 'h2' : 'h3', { className: 'md-h' }, inline(block.text, notePath))
        case 'p':
          return h('p', { className: 'md-p' }, inline(block.text, notePath))
        case 'list':
          return h('ul', { className: 'md-list' }, block.items.map((item, index) => h('li', { key: index }, inline(item, notePath))))
        case 'quote':
          return h('blockquote', { className: 'md-quote' }, block.lines.map((line, index) => h('p', { key: index }, inline(line, notePath))))
        case 'table':
          return h('div', { className: 'md-table-wrap' },
            h('table', { className: 'md-table' },
              h('thead', null, h('tr', null, block.header.map((cell, index) => h('th', { key: index }, inline(cell, notePath))))),
              h('tbody', null, block.rows.map((row, rowIndex) => h('tr', { key: rowIndex },
                row.map((cell, cellIndex) => h('td', { key: cellIndex }, inline(cell, notePath))))))))
        case 'code':
          return h('pre', { className: 'md-code' }, block.text)
        case 'hr':
          return h('hr', { className: 'md-hr' })
        default:
          return null
      }
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

    // ---------------- 页面 ----------------
    function Progress({ t }) {
      const percent = state.total > 0 ? Math.max(0, Math.min(100, Math.round((state.done / state.total) * 100))) : null
      return h('div', { className: 'vn-progress' },
        h('div', { className: 'vn-progress-label' },
          h('span', null, state.phase || t.preparing),
          h('span', null, percent === null ? '' : `${percent}%`)),
        h('div', { className: 'vn-bar' + (percent === null ? ' indeterminate' : '') },
          h('i', { style: percent === null ? undefined : { width: `${percent}%` } })))
    }

    function FetchPage({ t }) {
      const [copied, setCopied] = React.useState(false)
      const [showSource, setShowSource] = React.useState(false)
      const running = state.status === 'running'

      return h(React.Fragment, null,
        h('section', { className: 'vn-card' },
          h('div', { className: 'vn-card-body' },
            h('label', { className: 'vn-label', htmlFor: 'vn-target' }, t.target),
            h('input', {
              id: 'vn-target', className: 'vn-input', value: state.target, placeholder: t.targetHint,
              spellCheck: false,
              onChange: (event) => set({ target: event.target.value }),
              onKeyDown: (event) => { if (event.key === 'Enter') startFetch() },
            }),
            h('div', { className: 'vn-row' },
              h('div', null,
                h('label', { className: 'vn-label', htmlFor: 'vn-page' }, t.page),
                h('input', { id: 'vn-page', className: 'vn-input', type: 'number', min: 1, value: state.page, onChange: (event) => set({ page: event.target.value }) })),
              h('div', null,
                h('label', { className: 'vn-label', htmlFor: 'vn-frames' }, t.frames),
                h('input', { id: 'vn-frames', className: 'vn-input', type: 'number', min: 0, max: 30, value: state.frames, onChange: (event) => set({ frames: event.target.value }) }))),
            h('label', { className: 'vn-label', htmlFor: 'vn-outdir' }, t.outdir),
            h('div', { className: 'vn-outdir' },
              h('input', { id: 'vn-outdir', className: 'vn-input', value: state.outdir, placeholder: t.outdirHint, onChange: (event) => set({ outdir: event.target.value }) }),
              h('button', { type: 'button', className: 'vn-ghost', onClick: pickFolder }, t.pick)),
            h('label', { className: 'vn-label', htmlFor: 'vn-plan' }, t.plan),
            h('select', { id: 'vn-plan', className: 'vn-select', value: state.plan, onChange: (event) => set({ plan: event.target.value }) },
              h('option', { value: '' }, t.planNone),
              h('option', { value: 'vosk-cn' }, t.planVosk),
              h('option', { value: 'tiny' }, t.planTiny),
              h('option', { value: 'base' }, t.planBase),
              h('option', { value: 'small' }, t.planSmall)),
            h('p', { className: 'vn-hint' }, t.planHint),
            h('div', { className: 'vn-actions' },
              h('button', { className: 'vn-primary', disabled: running, onClick: startFetch },
                running ? t.running : t.go)),
            running ? h(Progress, { t }) : null,
            state.status === 'error' && state.error ? h('p', { className: 'vn-error' }, state.error) : null)),

        h('section', { className: 'vn-card vn-preview-card' },
          h('div', { className: 'vn-preview-head' },
            h('h2', null, t.preview),
            h('span', { className: 'vn-spacer' }),
            state.blocks.length
              ? h('button', { className: 'vn-ghost', onClick: () => setShowSource(!showSource) }, showSource ? t.preview : t.source)
              : null,
            state.note
              ? h('button', { className: 'vn-ghost', onClick: () => copyText(state.note).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1600) }) },
                  copied ? t.copied : t.copy)
              : null,
            state.notePath
              ? h('button', { className: 'vn-ghost', onClick: () => reveal(state.notePath, false) }, t.openFile)
              : null,
            state.notePath
              ? h('button', { className: 'vn-ghost', onClick: () => reveal(state.notePath, true) }, t.openFolder)
              : null,
            state.note ? h('button', { className: 'vn-ghost', onClick: () => downloadMarkdown(state.note) }, t.download) : null),
          h('div', { className: 'vn-preview-scroll' },
            state.warning ? h('p', { className: 'vn-warning' }, `${t.warning}：${state.warning}`) : null,
            !state.blocks.length
              ? h('div', { className: 'vn-empty' }, t.empty)
              : showSource
                ? h('pre', { className: 'md-code', style: { margin: 0, whiteSpace: 'pre-wrap' } }, state.note)
                : state.blocks.map((block, index) => h(Block, { key: index, block, notePath: state.notePath })))))
    }

    function SearchPage({ t }) {
      const results = state.results
      return h('section', { className: 'vn-card' },
        h('div', { className: 'vn-card-body', style: { display: 'flex', flexDirection: 'column', minHeight: 0 } },
          h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' } },
            h('div', { className: 'vn-seg' },
              h('button', { type: 'button', 'aria-pressed': state.searchKind === 'video', onClick: () => set({ searchKind: 'video' }) }, t.video),
              h('button', { type: 'button', 'aria-pressed': state.searchKind === 'author', onClick: () => set({ searchKind: 'author' }) }, t.user)),
            h('span', { className: 'vn-item-meta' }, t.fillTarget)),
          h('div', { className: 'vn-actions', style: { marginTop: 0 } },
            h('input', {
              className: 'vn-input', style: { flex: 1 }, value: state.keyword, placeholder: t.keywordHint, spellCheck: false,
              onChange: (event) => set({ keyword: event.target.value }),
              onKeyDown: (event) => { if (event.key === 'Enter') runSearch() },
            }),
            h('button', { className: 'vn-primary', disabled: state.searchStatus === 'searching', onClick: runSearch },
              state.searchStatus === 'searching' ? t.searching : t.search)),
          state.searchError ? h('p', { className: 'vn-error' }, state.searchError) : null,
          h('ul', { className: 'vn-list' },
            state.searchKind === 'video'
              ? results.map((video) => h('li', {
                  key: video.bvid,
                  className: 'vn-item',
                  onClick: () => set({ target: video.bvid, tab: 'fetch' }),
                },
                  h('div', { className: 'vn-item-title' }, video.title),
                  h('div', { className: 'vn-item-meta' },
                    h('span', null, video.author),
                    h('span', null, video.duration),
                    h('span', null, Number(video.play || 0).toLocaleString()))))
              : results.map((user) => h('li', { key: user.mid, className: 'vn-item' },
                  h('div', { className: 'vn-item-title' }, user.name),
                  h('div', { className: 'vn-item-meta' },
                    h('span', null, `${t.fans} ${Number(user.fans || 0).toLocaleString()}`),
                    h('span', null, `${t.videos} ${Number(user.videos || 0).toLocaleString()}`),
                    user.sign ? h('span', null, user.sign) : null,
                    h('a', { href: user.url, target: '_blank', rel: 'noreferrer' }, t.space)))),
            results.length === 0
              ? h('li', { className: 'vn-empty' }, state.searchStatus === 'done' ? t.noResult : t.emptySearch)
              : null)))
    }

    function LoginPage({ t }) {
      return h('section', { className: 'vn-card' },
        h('div', { className: 'vn-card-body' },
          h('label', { className: 'vn-label', htmlFor: 'vn-cookie' }, t.cookie),
          h('input', {
            id: 'vn-cookie', className: 'vn-input', type: 'password', value: state.cookie,
            placeholder: t.cookiePlaceholder, spellCheck: false,
            onChange: (event) => set({ cookie: event.target.value }),
          }),
          h('p', { className: 'vn-hint' }, t.cookieHint)))
    }

    function DownloadPage({ t }) {
      const deps = state.deps
      const installed = Boolean(deps?.installed) || Boolean(state.health?.engines?.whisper)
      const running = Boolean(deps?.running) || state.depsBusy
      return h('section', { className: 'vn-card' },
        h('div', { className: 'vn-card-body' },
          h('label', { className: 'vn-label', htmlFor: 'vn-channel' }, t.channel),
          h('select', { id: 'vn-channel', className: 'vn-select', value: state.channel, onChange: (event) => set({ channel: event.target.value }) },
            h('option', { value: 'auto' }, t.channelAuto),
            h('option', { value: 'official' }, t.channelOfficial),
            h('option', { value: 'mirror' }, t.channelMirror)),
          h('p', { className: 'vn-hint' }, t.channelHint),
          h('label', { className: 'vn-label' }, t.depsTitle),
          h('p', { className: 'vn-deps-state' },
            installed ? t.depsInstalled : (deps ? t.depsMissing : t.depsChecking)),
          running
            ? h('div', { className: 'vn-progress' },
                h('div', { className: 'vn-progress-label' },
                  h('span', null, deps?.phase || t.depsInstalling),
                  h('span', null, deps?.total > 0 ? `${Math.round((deps.done / deps.total) * 100)}%` : '')),
                h('div', { className: 'vn-bar' + (deps?.total > 0 ? '' : ' indeterminate') },
                  h('i', { style: deps?.total > 0 ? { width: `${Math.round((deps.done / deps.total) * 100)}%` } : undefined })))
            : h('div', { className: 'vn-actions' },
                h('button', { className: 'vn-primary', onClick: installDeps, disabled: installed }, t.depsInstall)),
          deps?.last_error ? h('p', { className: 'vn-error' }, String(deps.last_error)) : null))
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

    function LoginIcon() {
      return h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true },
        h('rect', { x: 4, y: 10, width: 16, height: 10, rx: 2 }),
        h('path', { d: 'M8 10V7a4 4 0 0 1 8 0v3' }))
    }

    function DownloadIcon() {
      return h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true },
        h('path', { d: 'M12 4v11' }),
        h('path', { d: 'm7 11 5 5 5-5' }),
        h('path', { d: 'M5 20h14' }))
    }

    const PAGES = {
      fetch: { nav: 'fetchNav', title: 'fetchTitle', sub: 'fetchSub', icon: FetchIcon },
      search: { nav: 'searchNav', title: 'searchTitle', sub: 'searchSub', icon: SearchIcon },
      login: { nav: 'loginNav', title: 'loginTitle', sub: 'loginSub', icon: LoginIcon },
      download: { nav: 'downloadNav', title: 'downloadTitle', sub: 'downloadSub', icon: DownloadIcon },
    }

    function VidnoteView() {
      const t = useT()
      useStore()

      React.useEffect(() => {
        if (!state.health) loadHealth()
        if (state.status === 'running' && state.jobId) pollJob(state.jobId)
        const heartbeat = setInterval(() => {
          fetch(`${API}/ping`).catch(() => {})
        }, 5000)
        return () => clearInterval(heartbeat)
      }, [])

      const page = PAGES[state.tab] ?? PAGES.fetch
      return h('div', { className: 'vn-view' },
        h('aside', { className: 'vn-side' },
          h('div', { className: 'vn-brand' },
            h('span', { className: 'vn-logo' }, 'V'),
            h('b', null, t.brand)),
          Object.entries(PAGES).map(([key, entry]) =>
            h('button', {
              key,
              type: 'button',
              className: 'vn-nav',
              'aria-current': state.tab === key,
              onClick: () => set({ tab: key }),
            },
              h(entry.icon),
              h('span', null, t[entry.nav]))),
          h('div', { className: 'vn-side-foot' },
            h('button', { type: 'button', className: 'vn-ghost', onClick: openWindow }, state.opened ? t.opened : t.legacy))),
        h('main', { className: 'vn-main' },
          h('div', { className: 'vn-topbar' },
            h('h1', null, t[page.title]),
            h('span', { className: 'vn-sub' }, t[page.sub]),
            h('span', { className: 'vn-spacer' })),
          h('div', { className: state.tab === 'fetch' ? 'vn-content' : 'vn-content-single' },
            state.tab === 'fetch'
              ? h(FetchPage, { t })
              : state.tab === 'search'
                ? h(SearchPage, { t })
                : state.tab === 'login'
                  ? h(LoginPage, { t })
                  : h(DownloadPage, { t }))))
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
            { name: 'conversation.view', id: 'vidnote', order: 20, label: () => currentText().viewLabel, locale: NS },
            VidnoteView,
          ))
      },
    }
  },
})
