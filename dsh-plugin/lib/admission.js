/**
 * DSH 本地接口的准入检查。
 *
 * 插件通过 webServer 注册的接口，必须走宿主的 connection.requestRejection：
 * 它同时做 Host/Origin 围栏和登录态校验。拿不到 connection 或它抛错时一律拒绝，
 * 不退回到只检查回环地址。
 */

function send(res, status, value) {
  if (res.destroyed || res.writableEnded) return
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
  })
  res.end(JSON.stringify(value))
}

/**
 * @param {unknown} connection 宿主的 connection 服务
 * @param {import('node:http').IncomingMessage} req
 * @param {import('node:http').ServerResponse} res
 * @returns {boolean} 已拒绝并写完响应时返回 true
 */
export function rejectRequest(connection, req, res) {
  let rejection
  try {
    if (typeof connection?.requestRejection !== 'function') throw new Error('admission unavailable')
    rejection = connection.requestRejection(req)
  } catch {
    send(res, 503, { error: '准入检查不可用' })
    return true
  }
  if (rejection !== undefined) {
    send(res, rejection === 401 ? 401 : 403, {
      error: rejection === 401 ? '需要登录 DSH' : '拒绝访问',
    })
    return true
  }
  return false
}

/** 包一层 handler，先过准入检查。 */
export function guarded(connection, handler) {
  return async (req, res) => {
    if (rejectRequest(connection, req, res)) return
    return handler(req, res)
  }
}
