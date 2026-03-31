const YOUTUBE_API_KEY = process.env.YOUTUBE_API_KEY!
const BASE_URL = 'https://www.googleapis.com/youtube/v3'

export type ChannelInfo = {
  channelId: string
  channelName: string
  description: string
  subscriberCount: number
  videoCount: number
  thumbnailUrl: string
}

export type TrendingVideo = {
  videoId: string
  title: string
  channelTitle: string
  viewCount: number
  description: string
  tags: string[]
}

export type SearchResult = {
  videoId: string
  title: string
  channelTitle: string
  publishedAt: string
  description: string
}

import { TopVideo } from './supabase'

function handleYouTubeError(data: Record<string, unknown>): never {
  const error = data.error as { code?: number; message?: string } | undefined
  if (error?.code === 403 && error.message?.includes('quota')) {
    throw new Error('YouTube API quota exceeded. Try again tomorrow.')
  }
  throw new Error(error?.message || 'YouTube API error')
}

export async function getChannelByUrl(url: string): Promise<ChannelInfo> {
  let identifier = ''
  let searchType = 'forHandle'

  try {
    const u = new URL(url)
    const pathParts = u.pathname.split('/').filter(Boolean)

    if (u.pathname.startsWith('/@')) {
      identifier = u.pathname.slice(2)
      searchType = 'forHandle'
    } else if (pathParts[0] === 'channel' && pathParts[1]) {
      identifier = pathParts[1]
      searchType = 'id'
    } else if (pathParts[0] === 'c' && pathParts[1]) {
      identifier = pathParts[1]
      searchType = 'forUsername'
    } else if (pathParts[0] && !pathParts[0].startsWith('@')) {
      identifier = pathParts[0]
      searchType = 'forUsername'
    } else {
      identifier = pathParts[0]?.replace('@', '') || ''
      searchType = 'forHandle'
    }
  } catch {
    // If URL parsing fails, treat as handle
    identifier = url.replace(/^@/, '').replace(/.*youtube\.com\/@?/, '')
    searchType = 'forHandle'
  }

  if (!identifier) {
    throw new Error('Could not parse YouTube channel URL. Try using the format: youtube.com/@handle')
  }

  const params = new URLSearchParams({
    part: 'snippet,statistics',
    key: YOUTUBE_API_KEY,
    [searchType]: identifier,
  })

  const res = await fetch(`${BASE_URL}/channels?${params}`)
  const data = await res.json()

  if (!res.ok) handleYouTubeError(data)

  if (!data.items || data.items.length === 0) {
    throw new Error(`YouTube channel not found for "${url}". Make sure the URL is correct.`)
  }

  const channel = data.items[0]
  return {
    channelId: channel.id,
    channelName: channel.snippet.title,
    description: channel.snippet.description || '',
    subscriberCount: parseInt(channel.statistics.subscriberCount || '0', 10),
    videoCount: parseInt(channel.statistics.videoCount || '0', 10),
    thumbnailUrl: channel.snippet.thumbnails?.high?.url || channel.snippet.thumbnails?.default?.url || '',
  }
}

export async function getTopVideos(channelId: string, maxResults: number = 20): Promise<TopVideo[]> {
  // Step 1: Get top video IDs via search
  const searchParams = new URLSearchParams({
    part: 'id',
    channelId,
    order: 'viewCount',
    type: 'video',
    maxResults: String(maxResults),
    key: YOUTUBE_API_KEY,
  })

  const searchRes = await fetch(`${BASE_URL}/search?${searchParams}`)
  const searchData = await searchRes.json()

  if (!searchRes.ok) handleYouTubeError(searchData)

  if (!searchData.items || searchData.items.length === 0) {
    return []
  }

  const videoIds = searchData.items.map((item: { id: { videoId: string } }) => item.id.videoId).join(',')

  // Step 2: Get full video details
  const videosParams = new URLSearchParams({
    part: 'snippet,statistics',
    id: videoIds,
    key: YOUTUBE_API_KEY,
  })

  const videosRes = await fetch(`${BASE_URL}/videos?${videosParams}`)
  const videosData = await videosRes.json()

  if (!videosRes.ok) handleYouTubeError(videosData)

  const videos: TopVideo[] = (videosData.items || []).map((v: {
    id: string
    snippet: { title: string; description: string; publishedAt: string; thumbnails?: { high?: { url: string }; default?: { url: string } } }
    statistics: { viewCount?: string; likeCount?: string }
  }) => ({
    videoId: v.id,
    title: v.snippet.title,
    viewCount: parseInt(v.statistics.viewCount || '0', 10),
    likeCount: parseInt(v.statistics.likeCount || '0', 10),
    description: v.snippet.description || '',
    publishedAt: v.snippet.publishedAt,
    thumbnailUrl: v.snippet.thumbnails?.high?.url || v.snippet.thumbnails?.default?.url || '',
  }))

  return videos.sort((a, b) => b.viewCount - a.viewCount)
}

export async function getTrendingVideos(regionCode: string = 'US'): Promise<TrendingVideo[]> {
  const params = new URLSearchParams({
    part: 'snippet,statistics',
    chart: 'mostPopular',
    regionCode,
    maxResults: '50',
    key: YOUTUBE_API_KEY,
  })

  const res = await fetch(`${BASE_URL}/videos?${params}`)
  const data = await res.json()

  if (!res.ok) handleYouTubeError(data)

  return (data.items || []).map((v: {
    id: string
    snippet: { title: string; channelTitle: string; description: string; tags?: string[] }
    statistics: { viewCount?: string }
  }) => ({
    videoId: v.id,
    title: v.snippet.title,
    channelTitle: v.snippet.channelTitle,
    viewCount: parseInt(v.statistics.viewCount || '0', 10),
    description: v.snippet.description || '',
    tags: v.snippet.tags || [],
  }))
}

export async function searchVideos(query: string, maxResults: number = 10): Promise<SearchResult[]> {
  const params = new URLSearchParams({
    part: 'snippet',
    q: query,
    type: 'video',
    maxResults: String(maxResults),
    key: YOUTUBE_API_KEY,
  })

  const res = await fetch(`${BASE_URL}/search?${params}`)
  const data = await res.json()

  if (!res.ok) handleYouTubeError(data)

  return (data.items || []).map((item: {
    id: { videoId: string }
    snippet: { title: string; channelTitle: string; publishedAt: string; description: string }
  }) => ({
    videoId: item.id.videoId,
    title: item.snippet.title,
    channelTitle: item.snippet.channelTitle,
    publishedAt: item.snippet.publishedAt,
    description: item.snippet.description || '',
  }))
}

export async function getVideoById(videoId: string): Promise<TopVideo | null> {
  const params = new URLSearchParams({
    part: 'snippet,statistics',
    id: videoId,
    key: YOUTUBE_API_KEY,
  })

  const res = await fetch(`${BASE_URL}/videos?${params}`)
  const data = await res.json()

  if (!res.ok) handleYouTubeError(data)

  if (!data.items || data.items.length === 0) return null

  const v = data.items[0]
  return {
    videoId: v.id,
    title: v.snippet.title,
    viewCount: parseInt(v.statistics.viewCount || '0', 10),
    likeCount: parseInt(v.statistics.likeCount || '0', 10),
    description: v.snippet.description || '',
    publishedAt: v.snippet.publishedAt,
    thumbnailUrl: v.snippet.thumbnails?.high?.url || v.snippet.thumbnails?.default?.url || '',
  }
}
