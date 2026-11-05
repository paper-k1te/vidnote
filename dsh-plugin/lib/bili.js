/**
 * 直接请求 B 站公开搜索接口：视频和 UP 主。
 *
 * vidnote 的 Python 层两种搜索都有，但命令行只暴露了视频搜索。插件不想为了一个
 * 参数去重建 105 MB 的 exe，所以这里用 fetch 走同一组公开接口：
 *
 *   - 视频： `/x/web-interface/search/all/v2`，取 result 里 result_type == "video" 的一组
 *   - UP 主：`/x/web-interface/search/type?search_type=bili_user`
 *
 * 不依赖 DSH，方便单测。
 */

const SEARCH_ALL = 'https://api.bilibili.com/x/web-interface/search/all/v2'
const SEARCH_TYPE = 'https://api.bilibili.com/x/web-interface/search/type'

const HEADERS = {
  'user-agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36',
  referer: 'https://www.bilibili.com/',
  accept: 'application/json, text/plain, */*',
}

/** 搜索结果里的标题/签名可能带高亮标签，去掉 HTML。 */
function plain(text) {
  return String(text ?? '')
    .replace(/<[^>]+>/g, '')
    .trim()
}

function https(url) {
  const value = String(url ?? '')
  if (value.startsWith('//')) return `https:${value}`
  if (value.startsWith('http://')) return `https://${value.slice(7)}`
  return value
}

/** 把接口返回的 data 变成 UP 主字段，方便单测。 */
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

/** all/v2 把结果按类型分组；取出视频那一组。 */
export function parseVideos(data, limit = 10) {
  const groups = Array.isArray(data?.result) ? data.result : []
  const group = groups.find((entry) => entry?.result_type === 'video')
  const items = Array.isArray(group?.data) ? group.data : []
  const videos = []
  for (const item of items) {
    const bvid = String(item?.bvid ?? '')
    if (!bvid || videos.length >= limit) continue
    videos.push({
      bvid,
      title: plain(item?.title),
      author: String(item?.author ?? ''),
      duration: String(item?.duration ?? ''),
      play: Number(item?.play ?? 0),
      url: `https://www.bilibili.com/video/${bvid}`,
    })
  }
  return videos
}

export function userSearchUrl(keyword, { page = 1 } = {}) {
  const query = new URLSearchParams({
    search_type: 'bili_user',
    keyword: String(keyword ?? '').trim(),
    page: String(page),
  })
  return `${SEARCH_TYPE}?${query}`
}

export function videoSearchUrl(keyword, { page = 1 } = {}) {
  const query = new URLSearchParams({
    keyword: String(keyword ?? '').trim(),
    page: String(page),
  })
  return `${SEARCH_ALL}?${query}`
}

async function requestJson(url, { fetchImpl, signal, label }) {
  let response
  try {
    response = await fetchImpl(url, { headers: HEADERS, signal })
  } catch (error) {
    throw new Error(`请求 B 站${label}接口失败：${error?.message ?? error}`)
  }

  if (!response.ok) throw new Error(`B 站${label}接口返回 HTTP ${response.status}。`)

  let payload
  try {
    payload = await response.json()
  } catch {
    throw new Error(`B 站${label}接口返回的不是 JSON，可能被风控了。`)
  }

  const code = Number(payload?.code ?? 0)
  if (code === -352) throw new Error('搜索被 B 站风控拦截（-352），稍后重试或降低频率。')
  if (code === -101) throw new Error('搜索接口现在要求登录（-101）。')
  if (code) throw new Error(`搜索失败 code=${code}: ${payload?.message ?? '未知错误'}`)
  return payload?.data
}

export async function searchUsers(
  keyword,
  { limit = 10, page = 1, fetchImpl = globalThis.fetch, signal } = {},
) {
  const word = String(keyword ?? '').trim()
  if (!word) throw new Error('搜索关键词不能为空。')
  if (typeof fetchImpl !== 'function') throw new Error('当前环境没有 fetch，无法搜索 UP 主。')
  const data = await requestJson(userSearchUrl(word, { page }), { fetchImpl, signal, label: '搜索' })
  return parseUsers(data, limit)
}

export async function searchVideos(
  keyword,
  { limit = 10, page = 1, fetchImpl = globalThis.fetch, signal } = {},
) {
  const word = String(keyword ?? '').trim()
  if (!word) throw new Error('搜索关键词不能为空。')
  if (typeof fetchImpl !== 'function') throw new Error('当前环境没有 fetch，无法搜索视频。')
  const data = await requestJson(videoSearchUrl(word, { page }), { fetchImpl, signal, label: '搜索' })
  return parseVideos(data, limit)
}
