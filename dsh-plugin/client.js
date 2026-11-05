// vidnote 的交互窗口：DSH 里只做一层壳，真正的界面还是 vidnote 自己的 serve-ui 页面。
// 宿主（index.js）负责把本地服务拉起来，这里通过 /vidnote/url 拿地址，再用 iframe 嵌入。
window.__ModuleLoader__.load({
  id: 'dsh-vidnote',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    let createPortal = null
    try {
      createPortal = require('react-dom').createPortal
    } catch {
      // 老宿主就在原地渲染
    }

    const ENDPOINT = '/vidnote/url'

    const TEXT = {
      title: 'vidnote',
      subtitle: 'B 站视频 → 带时间戳的 Markdown',
      open: 'B 站笔记',
      refresh: '重新加载',
      external: '在浏览器打开',
      close: '关闭',
      loading: '正在启动 vidnote 界面…',
      slow: '首次启动要解压单文件 exe，大约 3–5 秒。',
      error: 'vidnote 界面没能启动',
      retry: '重试',
    }

    const buttonStyle = {
      position: 'fixed',
      right: '24px',
      bottom: '118px',
      zIndex: 60,
      width: '46px',
      height: '46px',
      borderRadius: '50%',
      border: '1px solid var(--dsw-alias-border-l2, rgba(0,0,0,.12))',
      background: 'var(--dsw-alias-brand-primary, #4d6bfe)',
      color: '#fff',
      fontSize: '13px',
      fontWeight: 700,
      letterSpacing: '-0.02em',
      cursor: 'pointer',
      boxShadow: '0 6px 18px rgba(0,0,0,.22)',
      pointerEvents: 'auto',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }

    const backdropStyle = {
      position: 'fixed',
      inset: 0,
      zIndex: 9998,
      background: 'rgba(0,0,0,.45)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
      pointerEvents: 'auto',
    }

    const panelStyle = {
      width: 'min(1080px, 94vw)',
      height: 'min(780px, 88vh)',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--dsw-alias-bg-overlay, #fff)',
      color: 'var(--dsw-alias-label-primary, #111)',
      border: '1px solid var(--dsw-alias-border-l2, rgba(0,0,0,.12))',
      borderRadius: '14px',
      boxShadow: '0 24px 64px rgba(0,0,0,.35)',
      overflow: 'hidden',
    }

    const headerStyle = {
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      padding: '10px 14px',
      borderBottom: '1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.08))',
      flex: '0 0 auto',
    }

    const titleStyle = { fontWeight: 650, fontSize: '14px' }
    const subtitleStyle = {
      color: 'var(--dsw-alias-label-secondary, #666)',
      fontSize: '12px',
      marginLeft: '2px',
    }

    function actionStyle(primary) {
      return {
        marginLeft: 'auto',
        background: primary ? 'var(--dsw-alias-brand-primary, #4d6bfe)' : 'transparent',
        color: primary ? '#fff' : 'var(--dsw-alias-label-secondary, #555)',
        border: primary ? '0' : '1px solid var(--dsw-alias-border-l1, rgba(0,0,0,.12))',
        borderRadius: '8px',
        padding: '5px 10px',
        fontSize: '12px',
        cursor: 'pointer',
        whiteSpace: 'nowrap',
      }
    }

    function centerStyle() {
      return {
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '8px',
        padding: '24px',
        textAlign: 'center',
      }
    }

    function Frame({ url, reloadKey }) {
      return h('iframe', {
        key: reloadKey,
        src: url,
        title: 'vidnote',
        style: {
          flex: 1,
          width: '100%',
          border: '0',
          background: '#fff',
        },
      })
    }

    function Window({ onClose }) {
      const [state, setState] = React.useState({ status: 'loading' })
      const [attempt, setAttempt] = React.useState(0)
      const [reloadKey, setReloadKey] = React.useState(0)

      React.useEffect(() => {
        let alive = true
        setState({ status: 'loading' })
        fetch(ENDPOINT, { headers: { accept: 'application/json' } })
          .then((response) =>
            response.json().then((body) => ({
              ok: response.ok,
              status: response.status,
              body,
            })),
          )
          .then(({ ok, status, body }) => {
            if (!alive) return
            if (!ok || !body?.url) {
              setState({ status: 'error', message: body?.error ?? `HTTP ${status}` })
              return
            }
            setState({ status: 'ready', url: body.url })
          })
          .catch((error) => {
            if (alive) setState({ status: 'error', message: String(error?.message ?? error) })
          })
        return () => {
          alive = false
        }
      }, [attempt])

      const close = () => {
        if (typeof onClose === 'function') onClose()
      }

      const body = (() => {
        if (state.status === 'ready') {
          return h(Frame, { url: state.url, reloadKey })
        }
        if (state.status === 'error') {
          return h('div', { style: centerStyle() },
            h('div', { style: { fontWeight: 600 } }, TEXT.error),
            h('div', { style: { color: 'var(--dsw-alias-label-secondary, #666)', fontSize: '12px', maxWidth: '520px' } }, state.message),
            h('button', {
              style: actionStyle(true),
              onClick: () => setAttempt((value) => value + 1),
            }, TEXT.retry))
        }
        return h('div', { style: centerStyle() },
          h('div', { style: { fontWeight: 600 } }, TEXT.loading),
          h('div', { style: { color: 'var(--dsw-alias-label-secondary, #666)', fontSize: '12px' } }, TEXT.slow))
      })()

      const panel = h('div', { style: panelStyle, role: 'dialog', 'aria-label': 'vidnote' },
        h('div', { style: headerStyle },
          h('span', { style: titleStyle }, TEXT.title),
          h('span', { style: subtitleStyle }, TEXT.subtitle),
          state.status === 'ready'
            ? h('button', {
                style: actionStyle(false),
                onClick: () => setReloadKey((value) => value + 1),
              }, TEXT.refresh)
            : null,
          state.status === 'ready'
            ? h('button', {
                style: actionStyle(false),
                onClick: () => window.open(state.url, '_blank', 'noopener'),
              }, TEXT.external)
            : null,
          h('button', { style: actionStyle(false), onClick: close }, TEXT.close)),
        body)

      const backdrop = h('div', {
        style: backdropStyle,
        onMouseDown: (event) => {
          if (event.target === event.currentTarget) close()
        },
      }, panel)

      return createPortal ? createPortal(backdrop, document.body) : backdrop
    }

    function Launcher() {
      const [open, setOpen] = React.useState(false)

      React.useEffect(() => {
        if (!open) return undefined
        const onKey = (event) => {
          if (event.key === 'Escape') setOpen(false)
        }
        const previousOverflow = document.body.style.overflow
        document.body.style.overflow = 'hidden'
        window.addEventListener('keydown', onKey)
        return () => {
          window.removeEventListener('keydown', onKey)
          document.body.style.overflow = previousOverflow
        }
      }, [open])

      return h(React.Fragment, null,
        h('button', {
          type: 'button',
          style: buttonStyle,
          title: TEXT.open,
          'aria-label': TEXT.open,
          onClick: () => setOpen(true),
        }, 'B站'),
        open ? h(Window, { onClose: () => setOpen(false) }) : null)
    }

    return {
      inject: ['slots'],
      apply(ctx) {
        ctx.slots.inject('shell.overlay', () =>
          ctx.slots.register({
            name: 'shell.overlay',
            id: 'dsh-vidnote.window',
            order: 40,
          }, Launcher))
      },
    }
  },
})
