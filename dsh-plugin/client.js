// vid2note（原 vidnote）在 DSH 里的界面：注册成「对话 / 轨迹」旁边的第三个视图。
// 布局对齐 0.3.4 的新界面：左侧导航（抓取 / 搜索 / 登录 / 下载 / 历史 / 提示），
// 右侧「预览 / 关键帧 / 源文」三种视图 + 元数据头。
// 抓取/进度/关键帧/选目录/依赖安装都通过 /vidnote/app/api/* 代理给 vid2note 的 serve-ui。
// 状态放在模块级 store 里，切到「对话」再切回来不会丢。
window.__ModuleLoader__.load({
  id: 'dsh-vidnote',
  factory(require) {
    const React = require('react')
    const h = React.createElement

    const NS = 'dsh-vidnote'
    const ACCENT = '#f97316'
    const API = '/vidnote/app/api'
    const HISTORY_KEY = 'dsh-vidnote:history'
    const HISTORY_LIMIT = 24
    let localeFacade = null

    const TEXT = {
      zh: {
        brand: 'vid2note',
        viewLabel: 'vid2note',
        fetchNav: '抓取视频',
        searchNav: '搜索',
        loginNav: '登录 B 站',
        downloadNav: '下载',
        historyNav: '历史',
        tipsNav: '提示',
        fetchTitle: '抓取视频',
        fetchSub: '把 B 站视频变成带时间戳的 Markdown 笔记',
        searchTitle: '搜索',
        searchSub: '先找视频，挑一条再回来抓',
        loginTitle: '登录 B 站',
        loginSub: '可选，只用于读取登录后才可见的字幕',
        downloadTitle: '下载',
        downloadSub: 'whisper 依赖与模型下载渠道',
        historyTitle: '历史记录',
        historySub: '最近生成的笔记，点开就能重新查看',
        tipsTitle: '提示',
        tipsSub: '几个常用技巧',
        target: '链接或编号',
        targetHint: 'BV1xx411c7mD 或 https://www.bilibili.com/video/...',
        page: '分P',
        frames: '关键帧',
        outdir: '输出目录',
        outdirHint: '留空 = 默认目录',
        pick: '选择',
        paste: '粘贴',
        plan: '解析方案',
        planCloud: '云端转写 · 默认，需要 API Key',
        planGemini: 'Gemini · 音频直传，时间戳准',
        planWhisperApi: 'Whisper API · OpenAI 兼容接口',
        planNone: '不转写 · 只输出元数据',
        planVosk: 'Vosk 小模型 · 需本地安装',
        planTiny: 'whisper tiny · 本机，最快',
        planBase: 'whisper base · 本机，平衡',
        planSmall: 'whisper small · 本机，中文最好',
        planHint: '默认走云端转写；Key 填在「下载」页，或设置 GEMINI_API_KEY / OPENAI_API_KEY。',
        asrKey: '转写 API Key',
        asrBase: '转写接口地址（Whisper 兼容时填）',
        go: '生成笔记',
        running: '正在抓取…',
        preparing: '准备中…',
        preview: '预览',
        gallery: '关键帧',
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
        historyEmpty: '还没有历史记录，抓一条视频试试。',
        historyClear: '清空历史',
        historyDelete: '删除',
        historyLoad: '载入',
        historyWhen: '生成于',
        tips: [
          '搜到视频后点一下就把编号填进抓取页，按回车直接开始。',
          '多P 视频在「分P」里填第几集，时间戳链接会自动带上 &p=。',
          '关键帧数量默认 6 张；填 0 就不抽帧，生成更快。',
          '没有字幕时用「解析方案」里的 Vosk；whisper 要先在「下载」页装依赖。',
          '生成后可以切到「关键帧」「源文」，也可以打开文件或文件夹。',
          '历史记录只存在这个浏览器里，换设备不会同步。',
        ],
        legacy: '打开原界面',
        opened: '已打开窗口',
        hostStale: '宿主里的插件还是旧版本：请重启 DSH 后再试。',
        noResult: '没有找到结果。',
        error: '出错了',
        views: '播放',
        ready: '就绪',
        doneLabel: '完成',
        failed: '出错',
      },
      en: {
        brand: 'vid2note',
        viewLabel: 'vid2note',
        fetchNav: 'Fetch',
        searchNav: 'Search',
        loginNav: 'Sign in',
        downloadNav: 'Downloads',
        historyNav: 'History',
        tipsNav: 'Tips',
        fetchTitle: 'Fetch video',
        fetchSub: 'Turn a Bilibili video into timestamped Markdown',
        searchTitle: 'Search',
        searchSub: 'Find a video first, then come back to fetch it',
        loginTitle: 'Sign in to Bilibili',
        loginSub: 'Optional, only for subtitles that require a login',
        downloadTitle: 'Downloads',
        downloadSub: 'whisper dependencies and model download channel',
        historyTitle: 'History',
        historySub: 'Recently generated notes',
        tipsTitle: 'Tips',
        tipsSub: 'A few handy notes',
        target: 'Link or ID',
        targetHint: 'BV1xx411c7mD or https://www.bilibili.com/video/...',
        page: 'Part',
        frames: 'Keyframes',
        outdir: 'Output folder',
        outdirHint: 'Empty = default folder',
        pick: 'Choose',
        paste: 'Paste',
        plan: 'Transcription',
        planCloud: 'Cloud · default, needs an API key',
        planGemini: 'Gemini · audio upload, precise timestamps',
        planWhisperApi: 'Whisper API · OpenAI-compatible endpoint',
        planNone: 'Off · metadata only',
        planVosk: 'Vosk small · needs a local install',
        planTiny: 'whisper tiny · local, fastest',
        planBase: 'whisper base · local, balanced',
        planSmall: 'whisper small · local, best Chinese',
        planHint: 'Cloud transcription is the default; put the key on the Downloads page or set GEMINI_API_KEY / OPENAI_API_KEY.',
        asrKey: 'Transcription API key',
        asrBase: 'Transcription endpoint (for Whisper-compatible APIs)',
        go: 'Generate note',
        running: 'Fetching…',
        preparing: 'Preparing…',
        preview: 'Preview',
        gallery: 'Keyframes',
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
        historyEmpty: 'No history yet. Fetch a video first.',
        historyClear: 'Clear history',
        historyDelete: 'Delete',
        historyLoad: 'Load',
        historyWhen: 'Saved',
        tips: [
          'Click a search result to fill the id, then press Enter.',
          'For multi-part videos set the part number; links keep &p=.',
          'Keyframes default to 6; use 0 to skip them for a faster run.',
          'No subtitles? Pick Vosk; whisper needs its dependencies from Downloads.',
          'After a fetch, switch to Keyframes or Source, or open the file.',
          'History stays in this browser only.',
        ],
        legacy: 'Open app window',
        opened: 'Window opened',
        hostStale: 'The host still runs an older plugin. Restart DSH and try again.',
        noResult: 'Nothing found.',
        error: 'Something went wrong',
        views: 'plays',
        ready: 'Ready',
        doneLabel: 'Done',
        failed: 'Failed',
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

    function readHistory() {
      try {
        const raw = globalThis.localStorage?.getItem(HISTORY_KEY)
        const parsed = raw ? JSON.parse(raw) : []
        return Array.isArray(parsed) ? parsed : []
      } catch {
        return []
      }
    }

    function writeHistory(entries) {
      try {
        globalThis.localStorage?.setItem(HISTORY_KEY, JSON.stringify(entries))
        return true
      } catch {
        // 容量不够时丢掉正文，只留元数据
        try {
          const light = entries.map((entry) => ({ ...entry, note: '' }))
          globalThis.localStorage?.setItem(HISTORY_KEY, JSON.stringify(light))
        } catch {
          // 连元数据都存不下就放弃
        }
        return false
      }
    }

    const STYLES = `
.vn-view { display: flex; height: 100%; min-height: 0; background: var(--dsw-alias-bg-base, #fff); color: var(--dsw-alias-label-primary, #18181b); font-size: 13px; }
.vn-side { width: 188px; flex: none; display: flex; flex-direction: column; gap: 2px; padding: 12px 10px; background: var(--dsw-specific-sidebar-fill, var(--dsw-alias-bg-layer-2, #f5f5f7)); border-right: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08)); }
.vn-brand { display: flex; align-items: center; gap: 8px; padding: 4px 8px 14px; }
.vn-logo { width: 22px; height: 22px; border-radius: 6px; background: ${ACCENT}; color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; }
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
.vn-meta { display: flex; gap: 12px; padding: 12px 14px; border-bottom: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08)); }
.vn-cover { width: 120px; height: 68px; flex: none; object-fit: cover; border-radius: 6px; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.04)); }
.vn-meta-body { min-width: 0; display: flex; flex-direction: column; gap: 4px; justify-content: center; }
.vn-meta-title { font-size: 14px; font-weight: 600; line-height: 1.35; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.vn-chips { display: flex; flex-wrap: wrap; gap: 6px; font-size: 11.5px; color: var(--dsw-alias-label-secondary, #65656e); }
.vn-chip { padding: 1px 7px; border-radius: 999px; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.05)); }
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
.vn-ghost[aria-pressed="true"] { color: var(--dsw-alias-label-primary, #18181b); border-color: var(--dsw-alias-border-l2, rgba(0,0,0,.24)); background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.04)); }
.vn-tabs { display: inline-flex; gap: 2px; padding: 2px; border-radius: 7px; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.05)); }
.vn-tab { border: 0; background: transparent; color: var(--dsw-alias-label-secondary, #52525b); font-size: 12px; padding: 4px 11px; border-radius: 6px; cursor: pointer; }
.vn-tab[aria-selected="true"] { background: var(--dsw-alias-bg-base, #fff); color: var(--dsw-alias-label-primary, #18181b); font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.12); }
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
.md-img { display: block; max-width: 100%; margin: 8px 0; border-radius: 6px; border: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08)); cursor: zoom-in; }
.vn-gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; padding: 4px; }
.vn-frame { border: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08)); border-radius: 8px; overflow: hidden; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.03)); cursor: zoom-in; }
.vn-frame img { display: block; width: 100%; aspect-ratio: 16 / 9; object-fit: cover; }
.vn-frame span { display: block; padding: 4px 8px; font-size: 11px; color: var(--dsw-alias-label-secondary, #65656e); }
.vn-history { display: flex; flex-direction: column; gap: 8px; }
.vn-history-item { display: flex; gap: 10px; padding: 8px; border: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08)); border-radius: 8px; cursor: pointer; align-items: center; }
.vn-history-item:hover { background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.04)); }
.vn-history-item img { width: 96px; height: 54px; object-fit: cover; border-radius: 5px; flex: none; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.05)); }
.vn-history-body { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 3px; }
.vn-history-title { font-size: 13px; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vn-history-meta { font-size: 11.5px; color: var(--dsw-alias-label-secondary, #777); display: flex; gap: 8px; flex-wrap: wrap; }
.vn-list { list-style: none; margin: 10px 0 0; padding: 0; overflow: auto; }
.vn-item { display: flex; flex-direction: column; gap: 3px; padding: 8px; border-radius: 7px; cursor: pointer; }
.vn-item:hover { background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.04)); }
.vn-item-title { font-size: 13px; line-height: 1.45; }
.vn-search-cover { width: 96px; height: 54px; object-fit: cover; border-radius: 5px; flex: none; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.05)); }
.vn-item-meta { font-size: 11.5px; color: var(--dsw-alias-label-secondary, #777); display: flex; flex-wrap: wrap; gap: 8px; }
.vn-item-meta a { color: ${ACCENT}; text-decoration: none; }
.vn-seg { display: inline-flex; gap: 2px; padding: 2px; border-radius: 6px; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.05)); }
.vn-seg button { border: 0; background: transparent; color: var(--dsw-alias-label-secondary, #52525b); font-size: 12px; padding: 3px 10px; border-radius: 5px; cursor: pointer; }
.vn-seg button[aria-pressed="true"] { background: var(--dsw-alias-bg-base, #fff); color: var(--dsw-alias-label-primary, #18181b); font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.12); }
.vn-deps-state { font-size: 12px; color: var(--dsw-alias-label-secondary, #52525b); line-height: 1.6; margin: 6px 0 0; }
.vn-tips { margin: 0; padding-left: 18px; }
.vn-tips li { margin: 6px 0; line-height: 1.7; font-size: 13px; }

/* ---- 0.4.1 界面风格：渐变强调、药丸、封面头图、四步进度 ---- */
.vn-view { background: radial-gradient(1100px 380px at 18% -12%, rgba(251,114,153,.10), transparent 62%), radial-gradient(900px 320px at 92% 0%, rgba(249,115,22,.10), transparent 58%), var(--dsw-alias-bg-base, #fff); }
.vn-side { width: 184px; gap: 3px; }
.vn-brand { padding-bottom: 16px; }
.vn-logo { background: linear-gradient(135deg, #fb7299 0%, #f97316 100%); box-shadow: 0 6px 16px rgba(249,115,22,.32); }
.vn-nav { border-radius: 8px; position: relative; }
.vn-nav[aria-current="true"] { background: linear-gradient(90deg, rgba(249,115,22,.14), rgba(249,115,22,0)); font-weight: 600; }
.vn-nav[aria-current="true"]::before { content: ''; position: absolute; left: 2px; top: 6px; bottom: 6px; width: 3px; border-radius: 3px; background: linear-gradient(180deg, #fb7299, #f97316); }
.vn-topbar { height: 58px; }
.vn-status { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-size: 11.5px; background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.05)); color: var(--dsw-alias-label-secondary, #65656e); }
.vn-status i { width: 6px; height: 6px; border-radius: 50%; background: #94a3b8; display: inline-block; }
.vn-status.running i { background: #f97316; animation: vn-pulse 1.2s infinite; }
.vn-status.done i { background: #10b981; }
.vn-status.error i { background: #ef4444; }
@keyframes vn-pulse { 0%, 100% { opacity: 1 } 50% { opacity: .35 } }
.vn-card { border-radius: 14px; box-shadow: 0 10px 30px rgba(15,23,42,.06), 0 1px 2px rgba(15,23,42,.04); }
.vn-primary { background: linear-gradient(135deg, #fb7299 0%, #f97316 100%); box-shadow: 0 6px 16px rgba(249,115,22,.28); border-radius: 8px; }
.vn-primary:hover:not(:disabled) { background: linear-gradient(135deg, #fb7299 0%, #f97316 100%); filter: brightness(1.05); }
.vn-ghost { border-radius: 8px; }
.vn-chip { background: rgba(249,115,22,.12); color: var(--dsw-alias-label-primary, #18181b); }
.vn-hero { position: relative; margin: 12px 14px 0; height: 132px; border-radius: 12px; overflow: hidden; background: linear-gradient(135deg, rgba(251,114,153,.20), rgba(249,115,22,.20)); }
.vn-hero-cover { width: 100%; height: 100%; object-fit: cover; display: block; }
.vn-hero::after { content: ''; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0) 30%, rgba(0,0,0,.68) 100%); }
.vn-hero-body { position: absolute; left: 14px; right: 14px; bottom: 10px; z-index: 1; color: #fff; display: flex; flex-direction: column; gap: 4px; text-shadow: 0 1px 6px rgba(0,0,0,.4); }
.vn-hero-title { font-size: 15px; font-weight: 650; line-height: 1.35; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.vn-hero-chips { display: flex; flex-wrap: wrap; gap: 6px; font-size: 11px; }
.vn-hero-chips span { background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.22); padding: 1px 8px; border-radius: 999px; }
.vn-steps { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
.vn-step { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 11px; color: var(--dsw-alias-label-secondary, #65656e); background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.05)); }
.vn-step b { width: 6px; height: 6px; border-radius: 50%; background: currentColor; opacity: .35; }
.vn-step.active { color: #c2410c; background: rgba(249,115,22,.14); font-weight: 600; }
.vn-step.active b { opacity: 1; background: #f97316; }
.vn-step.done { color: #047857; background: rgba(16,185,129,.12); }
.vn-step.done b { opacity: 1; background: #10b981; }
.vn-pills { display: flex; gap: 6px; flex-wrap: wrap; }
.vn-pill { border: 1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.12)); background: transparent; border-radius: 999px; padding: 4px 12px; font-size: 12px; color: var(--dsw-alias-label-secondary, #52525b); cursor: pointer; }
.vn-pill[aria-pressed="true"] { border-color: transparent; background: linear-gradient(135deg, #fb7299, #f97316); color: #fff; font-weight: 600; }
.vn-version { display: inline-flex; align-items: center; gap: 6px; margin-top: 6px; padding: 4px 9px; border-radius: 999px; font-size: 11px; color: var(--dsw-alias-label-secondary, #777); background: var(--dsw-alias-bg-layer-2, rgba(0,0,0,.05)); }
.vn-frame { transition: transform .18s ease, box-shadow .18s ease; }
.vn-frame:hover { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(15,23,42,.12); }
`

    // ---------------- 会话内持久化的状态 ----------------
    const DEFAULT = {
      tab: 'fetch',
      target: '',
      page: '1',
      frames: '6',
      outdir: '',
      plan: 'cloud',
      asrKey: '',
      asrBase: '',
      asrLoaded: false,
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
      folder: '',
      meta: null,
      resultFrames: [],
      warning: '',
      error: '',
      previewTab: 'preview',
      searchKind: 'video',
      keyword: '',
      searchStatus: 'idle',
      results: [],
      searchError: '',
      health: null,
      deps: null,
      depsBusy: false,
      opened: false,
      history: [],
      historyLoaded: false,
    }
    let state = { ...DEFAULT }
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

    // ---------------- 历史记录 ----------------
    function saveHistory(result) {
      if (!result?.note) return
      const entry = {
        at: Date.now(),
        path: result.path ?? '',
        folder: result.folder ?? '',
        note: result.note,
        meta: result.meta ?? null,
        frames: Array.isArray(result.frames) ? result.frames : [],
      }
      const key = entry.path || entry.meta?.bvid || String(entry.at)
      const rest = state.history.filter((item) => (item.path || item.meta?.bvid) !== key)
      const history = [entry, ...rest].slice(0, HISTORY_LIMIT)
      writeHistory(history)
      set({ history })
    }

    function removeHistory(entry) {
      const history = state.history.filter((item) => item !== entry)
      writeHistory(history)
      set({ history })
    }

    function clearHistory() {
      writeHistory([])
      set({ history: [] })
    }

    async function loadHistoryEntry(entry) {
      set({
        tab: 'fetch',
        note: entry.note ?? '',
        notePath: entry.path ?? '',
        folder: entry.folder ?? '',
        meta: entry.meta ?? null,
        resultFrames: Array.isArray(entry.frames) ? entry.frames : [],
        previewTab: 'preview',
        error: '',
        warning: '',
      })
      if (!entry.note) {
        set({ blocks: [], error: '这条历史没有正文，只能看到元数据。' })
        return
      }
      try {
        const parsed = await fetch('/vidnote/parse', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ markdown: entry.note }),
        }).then((response) => response.json())
        set({ blocks: parsed.blocks ?? [] })
      } catch {
        set({ blocks: [] })
      }
    }

    // ---------------- 抓取任务 ----------------
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
            saveHistory(result)
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
              folder: result.folder ?? '',
              meta: result.meta ?? null,
              resultFrames: Array.isArray(result.frames) ? result.frames : [],
              warning: result.warning ?? '',
              phase: job.phase ?? '',
              previewTab: 'preview',
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
        error: '', warning: '', note: '', blocks: [], notePath: '', folder: '',
        meta: null, resultFrames: [], jobId: '', previewTab: 'preview',
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
            asr_key: state.asrKey.trim(),
            asr_base: state.asrBase.trim(),
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
        // 后端可能直接给数组，也可能包一层 { results }
        const results = Array.isArray(data) ? data : (data.results ?? [])
        set({ results, searchStatus: 'done' })
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

    function frameUrl(notePath, src) {
      return `${API}/frame?note=${encodeURIComponent(notePath)}&src=${encodeURIComponent(src)}`
    }

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
            nodes.push(h('img', {
              key,
              className: 'md-img',
              src: frameUrl(notePath, image[2]),
              alt: image[1],
              loading: 'lazy',
              referrerPolicy: 'no-referrer',
              onClick: () => window.open(frameUrl(notePath, image[2]), '_blank', 'noopener'),
            }))
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
      anchor.download = `${(first || 'vid2note').replace(/[\\/:*?"<>|]/g, '_').slice(0, 60)}.md`
      anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }

    // ---------------- 页面 ----------------
    const STEP_NAMES = ['元数据', '字幕/转写', '关键帧', '组装']

    /** 从后端 phase 文本猜当前在第几步，只用于进度展示。 */
    function stepOf(phase) {
      const text = String(phase ?? '')
      if (/关键帧/.test(text)) return 2
      if (/字幕|转写|音频|模型|下载/.test(text)) return 1
      if (/组装|写入|完成|笔记/.test(text)) return 3
      return 0
    }

    function Progress({ t }) {
      const percent = state.total > 0 ? Math.max(0, Math.min(100, Math.round((state.done / state.total) * 100))) : null
      const active = stepOf(state.phase)
      const finished = state.status === 'done'
      return h('div', { className: 'vn-progress' },
        h('div', { className: 'vn-progress-label' },
          h('span', null, state.phase || t.preparing),
          h('span', null, percent === null ? '' : `${percent}%`)),
        h('div', { className: 'vn-bar' + (percent === null ? ' indeterminate' : '') },
          h('i', { style: percent === null ? undefined : { width: `${percent}%` } })),
        h('div', { className: 'vn-steps' },
          STEP_NAMES.map((name, index) => h('span', {
            key: name,
            className: 'vn-step' + (finished || index < active ? ' done' : index === active ? ' active' : ''),
          }, h('b'), name))))
    }

    function formatDuration(value) {
      if (typeof value === 'number' && Number.isFinite(value)) {
        const total = Math.max(0, Math.floor(value))
        const hours = Math.floor(total / 3600)
        const minutes = Math.floor((total % 3600) / 60)
        const seconds = total % 60
        return hours
          ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
          : `${minutes}:${String(seconds).padStart(2, '0')}`
      }
      return String(value ?? '')
    }

    function MetaHeader({ t }) {
      const meta = state.meta
      if (!meta?.title) return null
      return h('div', { className: 'vn-hero' },
        meta.cover
          ? h('img', { className: 'vn-hero-cover', src: meta.cover, alt: '', referrerPolicy: 'no-referrer' })
          : null,
        h('div', { className: 'vn-hero-body' },
          h('div', { className: 'vn-hero-title' }, meta.title),
          h('div', { className: 'vn-hero-chips' },
            meta.author ? h('span', null, meta.author) : null,
            meta.bvid ? h('span', null, meta.bvid) : null,
            meta.duration ? h('span', null, formatDuration(meta.duration)) : null,
            meta.views ? h('span', null, `${Number(meta.views).toLocaleString()} ${t.views}`) : null)))
    }

    function galleryFrames() {
      if (state.resultFrames.length) return state.resultFrames
      const found = []
      const pattern = /!\[([^\]]*)\]\(<([^>]+)>\)/g
      let match
      while ((match = pattern.exec(state.note)) !== null) {
        found.push({ path: match[2], timestamp: '', alt: match[1] })
      }
      return found
    }

    function PreviewPane({ t }) {
      const [copied, setCopied] = React.useState(false)
      const frames = galleryFrames()

      const body = (() => {
        if (state.previewTab === 'source') {
          return state.note
            ? h('pre', { className: 'md-code', style: { margin: 0, whiteSpace: 'pre-wrap' } }, state.note)
            : h('div', { className: 'vn-empty' }, t.empty)
        }
        if (state.previewTab === 'gallery') {
          return frames.length
            ? h('div', { className: 'vn-gallery' },
                frames.map((frame, index) => h('div', {
                  key: `${frame.path}-${index}`,
                  className: 'vn-frame',
                  onClick: () => window.open(frameUrl(state.notePath, frame.path), '_blank', 'noopener'),
                },
                  h('img', { src: frameUrl(state.notePath, frame.path), alt: frame.alt ?? '', loading: 'lazy', referrerPolicy: 'no-referrer' }),
                  h('span', null, frame.timestamp ?? ''))))
            : h('div', { className: 'vn-empty' }, t.empty)
        }
        return state.blocks.length
          ? state.blocks.map((block, index) => h(Block, { key: index, block, notePath: state.notePath }))
          : h('div', { className: 'vn-empty' }, t.empty)
      })()

      return h('section', { className: 'vn-card vn-preview-card' },
        h('div', { className: 'vn-preview-head' },
          h('div', { className: 'vn-tabs', role: 'tablist' },
            h('button', { className: 'vn-tab', role: 'tab', 'aria-selected': state.previewTab === 'preview', onClick: () => set({ previewTab: 'preview' }) }, t.preview),
            h('button', { className: 'vn-tab', role: 'tab', 'aria-selected': state.previewTab === 'gallery', onClick: () => set({ previewTab: 'gallery' }) }, t.gallery),
            h('button', { className: 'vn-tab', role: 'tab', 'aria-selected': state.previewTab === 'source', onClick: () => set({ previewTab: 'source' }) }, t.source)),
          h('span', { className: 'vn-spacer' }),
          state.note
            ? h('button', { className: 'vn-ghost', onClick: () => copyText(state.note).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1600) }) },
                copied ? t.copied : t.copy)
            : null,
          state.notePath ? h('button', { className: 'vn-ghost', onClick: () => reveal(state.notePath, false) }, t.openFile) : null,
          state.notePath ? h('button', { className: 'vn-ghost', onClick: () => reveal(state.notePath, true) }, t.openFolder) : null,
          state.note ? h('button', { className: 'vn-ghost', onClick: () => downloadMarkdown(state.note) }, t.download) : null),
        h(MetaHeader, { t }),
        h('div', { className: 'vn-preview-scroll' },
          state.warning ? h('p', { className: 'vn-warning' }, `${t.warning}：${state.warning}`) : null,
          body))
    }

    function FetchPage({ t }) {
      const running = state.status === 'running'
      const paste = async () => {
        try {
          const text = await navigator.clipboard?.readText?.()
          if (text) set({ target: text.trim() })
        } catch {
          // 没有剪贴板权限时忽略
        }
      }
      return h(React.Fragment, null,
        h('section', { className: 'vn-card' },
          h('div', { className: 'vn-card-body' },
            h('label', { className: 'vn-label', htmlFor: 'vn-target' }, t.target),
            h('div', { className: 'vn-outdir' },
              h('input', {
                id: 'vn-target', className: 'vn-input', value: state.target, placeholder: t.targetHint,
                spellCheck: false,
                onChange: (event) => set({ target: event.target.value }),
                onKeyDown: (event) => { if (event.key === 'Enter') startFetch() },
              }),
              h('button', { type: 'button', className: 'vn-ghost', onClick: paste }, t.paste)),
            h('div', { className: 'vn-row' },
              h('div', null,
                h('label', { className: 'vn-label', htmlFor: 'vn-page' }, t.page),
                h('input', { id: 'vn-page', className: 'vn-input', type: 'number', min: 1, value: state.page, onChange: (event) => set({ page: event.target.value }) })),
              h('div', null,
                h('label', { className: 'vn-label' }, t.frames),
                h('div', { className: 'vn-pills' },
                  ['0', '3', '6', '12'].map((value) => h('button', {
                    key: value,
                    type: 'button',
                    className: 'vn-pill',
                    'aria-pressed': String(state.frames) === value,
                    onClick: () => set({ frames: value }),
                  }, value))))),
            h('label', { className: 'vn-label', htmlFor: 'vn-outdir' }, t.outdir),
            h('div', { className: 'vn-outdir' },
              h('input', { id: 'vn-outdir', className: 'vn-input', value: state.outdir, placeholder: t.outdirHint, onChange: (event) => set({ outdir: event.target.value }) }),
              h('button', { type: 'button', className: 'vn-ghost', onClick: pickFolder }, t.pick)),
            h('label', { className: 'vn-label', htmlFor: 'vn-plan' }, t.plan),
            h('select', { id: 'vn-plan', className: 'vn-select', value: state.plan, onChange: (event) => set({ plan: event.target.value }) },
              h('option', { value: 'cloud' }, t.planCloud),
              h('option', { value: 'gemini' }, t.planGemini),
              h('option', { value: 'whisper-api' }, t.planWhisperApi),
              h('option', { value: '' }, t.planNone),
              h('option', { value: 'vosk-cn' }, t.planVosk),
              h('option', { value: 'tiny' }, t.planTiny),
              h('option', { value: 'base' }, t.planBase),
              h('option', { value: 'small' }, t.planSmall)),
            h('p', { className: 'vn-hint' }, t.planHint),
            h('label', { className: 'vn-label', htmlFor: 'vn-asr-key' }, t.asrKey),
            h('input', {
              id: 'vn-asr-key', className: 'vn-input', type: 'password', value: state.asrKey,
              placeholder: 'Gemini Key / OpenAI Key', spellCheck: false,
              onChange: (event) => {
                set({ asrKey: event.target.value })
                try { localStorage.setItem('vid2note:asr-key', event.target.value) } catch { /* 忽略 */ }
              },
            }),
            h('label', { className: 'vn-label', htmlFor: 'vn-asr-base' }, t.asrBase),
            h('input', {
              id: 'vn-asr-base', className: 'vn-input', value: state.asrBase,
              placeholder: 'https://api.openai.com/v1', spellCheck: false,
              onChange: (event) => {
                set({ asrBase: event.target.value })
                try { localStorage.setItem('vid2note:asr-base', event.target.value) } catch { /* 忽略 */ }
              },
            }),
            h('div', { className: 'vn-actions' },
              h('button', { className: 'vn-primary', disabled: running, onClick: startFetch },
                running ? t.running : t.go)),
            running ? h(Progress, { t }) : null,
            state.status === 'error' && state.error ? h('p', { className: 'vn-error' }, state.error) : null)),
        h(PreviewPane, { t }))
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
                  h('div', { style: { display: 'flex', gap: '10px', alignItems: 'center' } },
                    video.cover
                      ? h('img', { className: 'vn-search-cover', src: video.cover, alt: '', loading: 'lazy', referrerPolicy: 'no-referrer' })
                      : null,
                    h('div', { style: { minWidth: 0 } },
                      h('div', { className: 'vn-item-title' }, video.title),
                      h('div', { className: 'vn-item-meta' },
                        h('span', null, video.author),
                        h('span', null, video.duration),
                        h('span', null, Number(video.play || 0).toLocaleString()))))))
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

    function HistoryPage({ t }) {
      return h('section', { className: 'vn-card' },
        h('div', { className: 'vn-card-body', style: { display: 'flex', flexDirection: 'column', minHeight: 0 } },
          h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px' } },
            h('span', { className: 'vn-hint', style: { margin: 0, flex: 1 } }, t.historySub),
            h('button', { className: 'vn-ghost', onClick: clearHistory, disabled: state.history.length === 0 }, t.historyClear)),
          state.history.length === 0
            ? h('div', { className: 'vn-empty' }, t.historyEmpty)
            : h('div', { className: 'vn-history', style: { marginTop: '10px' } },
                state.history.map((entry, index) => h('div', {
                  key: `${entry.path}-${index}`,
                  className: 'vn-history-item',
                  onClick: () => loadHistoryEntry(entry),
                },
                  entry.meta?.cover
                    ? h('img', { src: entry.meta.cover, alt: '', referrerPolicy: 'no-referrer', loading: 'lazy' })
                    : h('div', { className: 'vn-history-item' , style: { width: '96px', height: '54px', padding: 0, cursor: 'default' } }),
                  h('div', { className: 'vn-history-body' },
                    h('div', { className: 'vn-history-title' }, entry.meta?.title || entry.path || '未命名'),
                    h('div', { className: 'vn-history-meta' },
                      entry.meta?.author ? h('span', null, entry.meta.author) : null,
                      entry.meta?.duration ? h('span', null, formatDuration(entry.meta.duration)) : null,
                      h('span', null, `${t.historyWhen} ${new Date(entry.at).toLocaleString()}`))),
                  h('button', {
                    className: 'vn-ghost',
                    onClick: (event) => { event.stopPropagation(); removeHistory(entry) },
                  }, t.historyDelete))))))
    }

    function TipsPage({ t }) {
      return h('section', { className: 'vn-card' },
        h('div', { className: 'vn-card-body' },
          h('ul', { className: 'vn-tips' }, t.tips.map((tip, index) => h('li', { key: index }, tip)))))
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

    function HistoryIcon() {
      return h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true },
        h('path', { d: 'M3 12a9 9 0 1 0 3-6.7' }),
        h('path', { d: 'M3 4v5h5' }),
        h('path', { d: 'M12 8v5l3 2' }))
    }

    function TipsIcon() {
      return h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true },
        h('circle', { cx: 12, cy: 12, r: 9 }),
        h('path', { d: 'M12 11v5' }),
        h('path', { d: 'M12 8h.01' }))
    }

    const PAGES = {
      fetch: { nav: 'fetchNav', title: 'fetchTitle', sub: 'fetchSub', icon: FetchIcon },
      search: { nav: 'searchNav', title: 'searchTitle', sub: 'searchSub', icon: SearchIcon },
      login: { nav: 'loginNav', title: 'loginTitle', sub: 'loginSub', icon: LoginIcon },
      download: { nav: 'downloadNav', title: 'downloadTitle', sub: 'downloadSub', icon: DownloadIcon },
      history: { nav: 'historyNav', title: 'historyTitle', sub: 'historySub', icon: HistoryIcon },
      tips: { nav: 'tipsNav', title: 'tipsTitle', sub: 'tipsSub', icon: TipsIcon },
    }

    function VidnoteView() {
      const t = useT()
      useStore()

      React.useEffect(() => {
        if (!state.health) loadHealth()
        if (!state.historyLoaded) set({ history: readHistory(), historyLoaded: true })
        if (!state.asrLoaded) {
          let asrKey = ''
          let asrBase = ''
          try {
            asrKey = globalThis.localStorage?.getItem('vid2note:asr-key') || ''
            asrBase = globalThis.localStorage?.getItem('vid2note:asr-base') || ''
          } catch {
            // 没有 localStorage 时留空
          }
          set({ asrKey, asrBase, asrLoaded: true })
        }
        if (state.status === 'running' && state.jobId) pollJob(state.jobId)
        const heartbeat = setInterval(() => {
          fetch(`${API}/ping`).catch(() => {})
        }, 5000)
        return () => clearInterval(heartbeat)
      }, [])

      const page = PAGES[state.tab] ?? PAGES.fetch
      const pageBody = (() => {
        switch (state.tab) {
          case 'search': return h(SearchPage, { t })
          case 'login': return h(LoginPage, { t })
          case 'download': return h(DownloadPage, { t })
          case 'history': return h(HistoryPage, { t })
          case 'tips': return h(TipsPage, { t })
          default: return h(FetchPage, { t })
        }
      })()

      const statusText = state.status === 'running'
        ? `${t.running}${state.total > 0 ? ` ${Math.round((state.done / state.total) * 100)}%` : ''}`
        : state.status === 'done' ? t.doneLabel : state.status === 'error' ? t.failed : t.ready

      return h('div', { className: 'vn-view' },
        h('aside', { className: 'vn-side' },
          h('div', { className: 'vn-brand' },
            h('span', { className: 'vn-logo' }, 'v2'),
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
            h('span', { className: 'vn-version' }, 'v0.4.1 · Tauri'),
            h('button', { type: 'button', className: 'vn-ghost', onClick: openWindow }, state.opened ? t.opened : t.legacy))),
        h('main', { className: 'vn-main' },
          h('div', { className: 'vn-topbar' },
            h('h1', null, t[page.title]),
            h('span', { className: 'vn-sub' }, t[page.sub]),
            h('span', { className: 'vn-spacer' }),
            h('span', { className: `vn-status ${state.status}` }, h('i'), statusText)),
          h('div', { className: state.tab === 'fetch' ? 'vn-content' : 'vn-content-single' }, pageBody)))
    }

    return {
      inject: ['slots'],
      apply(ctx) {
        // 先把视图注册上，再处理样式/语言：任何一步出问题都不该让标签消失。
        ctx.slots.inject('conversation.view', () =>
          ctx.slots.register(
            { name: 'conversation.view', id: 'vidnote', order: 20, label: () => currentText().viewLabel, locale: NS },
            VidnoteView,
          ))

        try {
          const locale = ctx.get('locale')
          localeFacade = locale
            ? {
                subscribe: (listener) => locale.subscribe(listener),
                getSnapshot: () => locale.getSnapshot(),
              }
            : null
        } catch {
          localeFacade = null
        }

        try {
          ctx.effect(() => {
            const style = document.createElement('style')
            style.textContent = STYLES
            document.head.appendChild(style)
            return () => style.remove()
          }, 'vidnote: styles')
        } catch {
          // 样式注入失败时仍然保留视图
        }
      },
    }
  },
})
