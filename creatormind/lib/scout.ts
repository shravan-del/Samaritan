import { getTrendingVideos } from './youtube'
import Anthropic from '@anthropic-ai/sdk'

export type TrendSignal = {
  source: 'youtube_trending' | 'reddit' | 'web_search'
  title: string
  description: string
  url: string
  engagement: string
  niche_relevance: string
}

function formatViewCount(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M views`
  if (count >= 1_000) return `${(count / 1_000).toFixed(0)}K views`
  return `${count} views`
}

function getNicheSubreddits(niche: string): string[] {
  const n = niche.toLowerCase()
  const base = ['youtubers', 'NewTubers', 'creators', 'videography']

  if (n.includes('gaming') || n.includes('game')) {
    return [...base, 'gaming', 'GameDeals', 'pcgaming', 'indiegaming']
  }
  if (n.includes('tech') || n.includes('software') || n.includes('code') || n.includes('dev')) {
    return [...base, 'technology', 'gadgets', 'hardware', 'programming', 'webdev']
  }
  if (n.includes('finance') || n.includes('invest') || n.includes('money') || n.includes('crypto')) {
    return [...base, 'investing', 'personalfinance', 'stocks', 'financialindependence']
  }
  if (n.includes('fitness') || n.includes('gym') || n.includes('health') || n.includes('workout')) {
    return [...base, 'fitness', 'xxfitness', 'bodybuilding', 'loseit']
  }
  if (n.includes('cook') || n.includes('food') || n.includes('recipe') || n.includes('chef')) {
    return [...base, 'Cooking', 'food', 'recipes', 'MealPrepSunday']
  }
  if (n.includes('travel') || n.includes('vlog')) {
    return [...base, 'travel', 'solotravel', 'backpacking', 'digitalnomad']
  }
  if (n.includes('beauty') || n.includes('makeup') || n.includes('skincare')) {
    return [...base, 'beauty', 'MakeupAddiction', 'SkincareAddiction']
  }
  if (n.includes('music') || n.includes('produc') || n.includes('audio')) {
    return [...base, 'WeAreTheMusicMakers', 'edmproduction', 'makinghiphop']
  }
  if (n.includes('education') || n.includes('learn') || n.includes('study')) {
    return [...base, 'learnprogramming', 'AskAcademia', 'GetStudying']
  }
  if (n.includes('business') || n.includes('entrepreneur') || n.includes('startup')) {
    return [...base, 'entrepreneur', 'smallbusiness', 'startups']
  }

  return [...base, 'videos', 'OutOfTheLoop', 'TrueOffMyChest']
}

async function scoreTrendRelevance(
  videoTitle: string,
  videoDescription: string,
  niche: string
): Promise<number> {
  try {
    const client = new Anthropic()
    const msg = await client.messages.create({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 10,
      messages: [
        {
          role: 'user',
          content: `Score 0-10 how relevant this YouTube trending video is to the niche "${niche}". Reply with ONLY a single integer.

Video: "${videoTitle}"
Description: "${videoDescription.slice(0, 200)}"`,
        },
      ],
    })

    const text = (msg.content[0] as { type: string; text: string }).text.trim()
    const score = parseInt(text, 10)
    return isNaN(score) ? 0 : Math.min(10, Math.max(0, score))
  } catch {
    return 0
  }
}

async function scoutYouTubeTrending(niche: string): Promise<TrendSignal[]> {
  const videos = await getTrendingVideos('US')

  const scored = await Promise.all(
    videos.map(async (v) => ({
      video: v,
      score: await scoreTrendRelevance(v.title, v.description, niche),
    }))
  )

  return scored
    .filter((s) => s.score >= 6)
    .map((s) => ({
      source: 'youtube_trending' as const,
      title: s.video.title,
      description: s.video.description.slice(0, 300),
      url: `https://www.youtube.com/watch?v=${s.video.videoId}`,
      engagement: formatViewCount(s.video.viewCount),
      niche_relevance: `Relevance score: ${s.score}/10`,
    }))
}

async function scoutReddit(niche: string): Promise<TrendSignal[]> {
  const subreddits = getNicheSubreddits(niche)
  const signals: TrendSignal[] = []

  await Promise.allSettled(
    subreddits.map(async (sub) => {
      try {
        const res = await fetch(`https://www.reddit.com/r/${sub}/hot.json?limit=25`, {
          headers: { 'User-Agent': 'CreatorMind/1.0' },
          signal: AbortSignal.timeout(8000),
        })

        if (!res.ok) return

        const data = await res.json()
        const posts = data?.data?.children || []

        for (const post of posts) {
          const p = post.data
          if (p.score < 300 || p.is_self === false && !p.title) continue

          signals.push({
            source: 'reddit' as const,
            title: p.title,
            description: (p.selftext || p.url || '').slice(0, 300),
            url: `https://www.reddit.com${p.permalink}`,
            engagement: `${p.score.toLocaleString()} upvotes, ${p.num_comments} comments`,
            niche_relevance: `r/${sub}`,
          })
        }
      } catch {
        // Silent fail per subreddit
      }
    })
  )

  return signals
}

async function scoutWebSearch(niche: string, contentPillars: string[]): Promise<TrendSignal[]> {
  const queries = [
    `${niche} YouTube trending 2026`,
    `viral ${niche} content ideas creators`,
    `${contentPillars[0] || niche} TikTok trend YouTube`,
  ]

  const signals: TrendSignal[] = []

  await Promise.allSettled(
    queries.map(async (q) => {
      try {
        const res = await fetch('https://google.serper.dev/search', {
          method: 'POST',
          headers: {
            'X-API-KEY': process.env.SERPER_API_KEY!,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ q, num: 10, gl: 'us' }),
          signal: AbortSignal.timeout(8000),
        })

        if (!res.ok) return

        const data = await res.json()
        const organic = data.organic || []

        for (const result of organic) {
          signals.push({
            source: 'web_search' as const,
            title: result.title || '',
            description: result.snippet || '',
            url: result.link || '',
            engagement: `Rank ${result.position || 0} in Google`,
            niche_relevance: `Query: "${q}"`,
          })
        }
      } catch {
        // Silent fail per query
      }
    })
  )

  return signals
}

export async function scoutTrends(niche: string, contentPillars: string[]): Promise<TrendSignal[]> {
  const results = await Promise.allSettled([
    scoutYouTubeTrending(niche),
    scoutReddit(niche),
    scoutWebSearch(niche, contentPillars),
  ])

  const allSignals: TrendSignal[] = []

  for (const result of results) {
    if (result.status === 'fulfilled') {
      allSignals.push(...result.value)
    }
  }

  // Deduplicate by URL
  const seen = new Set<string>()
  const deduped = allSignals.filter((s) => {
    if (seen.has(s.url)) return false
    seen.add(s.url)
    return true
  })

  // Shuffle to mix sources
  for (let i = deduped.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[deduped[i], deduped[j]] = [deduped[j], deduped[i]]
  }

  return deduped.slice(0, 45)
}
