/**
 * 直接请求 B 站搜索接口，查 UP 主（作者）。
 *
 * vidnote 的 Python 层已经有作者搜索，但命令行只暴露了视频搜索，插件又不想为了
 * 一个新参数去重建 105 MB 的 exe——所以这里用 fetch 走同一个公开接口：
 * `/x/web-interface/search/type?search_type=bili_user`。
 *
 * 不依赖 DSH，方便单测。
 */

const API = 'https://api.bilibili.com/x/web-interface/search/type'

const HEADERS = {
  'user-agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36',
  referer: 'https://www.bilibili.com/',
  accept: 'application/json, text/plain, */*',
}

/** 搜索结果里的签名/昵称可能带高亮标签，去掉 HTML。 */
function plain(text) {
  return String(text ?? '').replace(/<[^>]+>/g, '').trim()
}

function https(url) {
  const value = String(url ?? '')
  if (value.startsWith('//')) return `https:${value}`
  if (value.startsWith('http://')) return `https://${value.slice(7)}`
  return value
}

/** 把接口返回的 data 变成插件对外的字段，方便单测。 */
export function parseUsers(data, limit = 10) {
  const items = Array.isArray(data?.result) ? data.result : []
  const users = []
  for (const item of items) {
    const mid = Number(item?.mid ?? 0)
    if (!mid || users.length >= limit) continue
    const verify = item?.official_verify ?? {}
    users.push({
      mid,
      name: plain(item?.uname),
      fans: Number(item?.fans ?? 0),
      videos: Number(item?.videos ?? 0),
      sign: plain(item?.usign),
      verified: plain(verify.desc),
      avatar: https(item?.upic),
      url: `https://space.bilibili.com/${mid}`,
    })
  }
  return users
}

export function userSearchUrl(keyword, { limit = 10, page = 1 } = {}) {
  const query = new URLSearchParams({
    search_type: 'bili_user',
    keyword: String(keyword ?? '').trim(),
    page: String(page),
  })
  // 接口没有条数参数，多取一些再自己截断
  return `${API}?${query}`
}

export async function searchUsers(
  keyword,
  { limit = 10, page = 1, fetchImpl = globalThis.fetch, signal } = {},
) {
  const word = String(keyword ?? '').trim()
  if (!word) throw new Error('搜索关键词不能为空。')
  if (typeof fetchImpl !== 'function') throw new Error('当前环境没有 fetch，无法搜索 UP 主。')

  let response
  try {
    response = await fetchImpl(userSearchUrl(word, { limit, page }), {
      headers: HEADERS,
      signal,
    })
  } catch (error) {
    throw new Error(`请求 B 站搜索接口失败：${error?.message ?? error}`)
  }

  if (!response.ok) throw new Error(`B 站搜索接口返回 HTTP ${response.status}。`)

  let payload
  try {
    payload = await response.json()
  } catch {
    throw new Error('B 站搜索接口返回的不是 JSON，可能被风控了。')
  }

  const code = Number(payload?.code ?? 0)
  if (code === -352) throw new Error('搜索被 B 站风控拦截（-352），稍后重试或降低频率。')
  if (code === -101) throw new Error('搜索接口现在要求登录（-101）。')
  if (code) throw new Error(`搜索失败 code=${code}: ${payload?.message ?? '未知错误'}`)

  return parseUsers(payload?.data, limit)
}
