import { NextResponse } from 'next/server'
import { z } from 'zod'
import { supabaseAdmin } from '@/lib/supabase'
import { getAuthUser } from '@/lib/auth'
import { getChannelByUrl, getTopVideos, getVideoById } from '@/lib/youtube'
import { buildCreatorProfile } from '@/lib/anthropic'

const schema = z.object({
  channelUrl: z.string().optional(),
  topVideoUrls: z.string().optional(),
  story: z.string().min(10),
  goals: z.string().min(10),
  inspirations: z.string(),
  postingFrequency: z.string(),
  targetAudience: z.string(),
  avoidTopics: z.string(),
  styleWords: z.string(),
  biggestChallenge: z.string(),
})

function extractVideoId(url: string): string | null {
  try {
    const u = new URL(url)
    if (u.searchParams.has('v')) return u.searchParams.get('v')
    const match = url.match(/youtu\.be\/([^?&]+)/)
    if (match) return match[1]
  } catch {}
  return null
}

async function triggerFirstScout(creatorId: string): Promise<void> {
  // Fire-and-forget: run scout logic inline
  const { scoutTrends } = await import('@/lib/scout')
  const { generateVideoIdeas } = await import('@/lib/anthropic')

  const admin = supabaseAdmin()

  const { data: creator } = await admin
    .from('creators')
    .select('*')
    .eq('id', creatorId)
    .single()

  if (!creator || !creator.profile_built) return

  const weekOf = thisMonday()
  const trends = await scoutTrends(creator.niche || '', creator.content_pillars || [])
  const result = await generateVideoIdeas({ creator, trends, weekOf })

  const ideas = result.ideas.map((idea) => ({
    creator_id: creatorId,
    title: idea.title,
    hook: idea.hook,
    description: idea.description,
    thumbnail_concept: idea.thumbnailConcept,
    format: idea.format,
    viral_score: idea.viralScore,
    trend_source: idea.trendSource,
    trend_url: idea.trendUrl,
    why_now: idea.whyNow,
    estimated_views: idea.estimatedViews,
    week_of: weekOf,
    status: 'new',
  }))

  await admin.from('video_ideas').insert(ideas)

  const pivots = result.pivots.map((p) => ({
    creator_id: creatorId,
    niche: p.niche,
    rationale: p.rationale,
    example_channels: p.exampleChannels,
    difficulty: p.difficulty,
    revenue_potential: p.revenuePotential,
    week_of: weekOf,
  }))

  await admin.from('pivot_opportunities').insert(pivots)
  await admin.from('weekly_briefs').upsert({
    creator_id: creatorId,
    week_of: weekOf,
    summary: '',
    format_to_steal: result.formatToSteal,
    platform_insight: result.platformInsight,
    calendar: [],
  }, { onConflict: 'creator_id,week_of' })

  await admin.from('scout_runs').insert({
    creator_id: creatorId,
    sources_checked: trends.length,
    ideas_generated: ideas.length,
  })
}

function thisMonday(): string {
  const now = new Date()
  const day = now.getDay()
  const diff = now.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(now.setDate(diff))
  return monday.toISOString().split('T')[0]
}

export async function POST(req: Request) {
  try {
    const user = await getAuthUser(req)
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await req.json()
    const parsed = schema.safeParse(body)

    if (!parsed.success) {
      return NextResponse.json(
        { error: 'Validation error', details: parsed.error.flatten() },
        { status: 400 }
      )
    }

    const data = parsed.data
    const admin = supabaseAdmin()

    // Step 2: Fetch channel data if URL provided
    let channelId: string | null = null
    let channelName: string = 'My Channel'
    let channelDescription: string = ''
    let subscriberCount: number | null = null
    let totalVideos: number | null = null
    let topVideos: Awaited<ReturnType<typeof getTopVideos>> = []

    if (data.channelUrl) {
      try {
        const channelInfo = await getChannelByUrl(data.channelUrl)
        channelId = channelInfo.channelId
        channelName = channelInfo.channelName
        channelDescription = channelInfo.description
        subscriberCount = channelInfo.subscriberCount
        totalVideos = channelInfo.videoCount

        topVideos = await getTopVideos(channelId, 20)
      } catch (err) {
        console.error('YouTube fetch failed (non-fatal):', err)
      }
    }

    // Step 3: Parse individual video URLs if provided
    if (data.topVideoUrls && topVideos.length === 0) {
      const urls = data.topVideoUrls.split('\n').map((u: string) => u.trim()).filter(Boolean)
      const videoFetches = await Promise.allSettled(
        urls.map(async (url: string) => {
          const videoId = extractVideoId(url)
          if (!videoId) return null
          return getVideoById(videoId)
        })
      )
      for (const result of videoFetches) {
        if (result.status === 'fulfilled' && result.value) {
          topVideos.push(result.value)
        }
      }
    }

    // Step 4: Build creator profile
    const profile = await buildCreatorProfile({
      channelName,
      channelDescription,
      topVideos: topVideos.map((v) => ({
        title: v.title,
        viewCount: v.viewCount,
        description: v.description,
        publishedAt: v.publishedAt,
      })),
      story: data.story,
      goals: data.goals,
      inspirations: data.inspirations,
      postingFrequency: data.postingFrequency,
      targetAudience: data.targetAudience,
      avoidTopics: data.avoidTopics,
      styleWords: data.styleWords,
      biggestChallenge: data.biggestChallenge,
    })

    // Step 5: Upsert creator record
    const { data: creatorRow, error: upsertError } = await admin
      .from('creators')
      .upsert(
        {
          user_id: user.id,
          channel_url: data.channelUrl || null,
          channel_id: channelId,
          channel_name: channelName,
          channel_description: channelDescription,
          subscriber_count: subscriberCount,
          total_videos: totalVideos,
          top_videos: topVideos,
          niche: profile.niche,
          content_pillars: profile.contentPillars,
          target_audience: profile.audienceDescription,
          creator_voice: profile.creatorVoice,
          strength_topics: profile.strengthTopics,
          avoid_topics: profile.avoidTopics,
          content_style: profile.contentStyle,
          unique_angle: profile.uniqueAngle,
          goals: data.goals,
          story: data.story,
          inspirations: data.inspirations,
          posting_frequency: data.postingFrequency,
          biggest_challenge: data.biggestChallenge,
          style_words: data.styleWords,
          profile_built: true,
          status: 'trial',
        },
        { onConflict: 'user_id' }
      )
      .select('id')
      .single()

    if (upsertError) {
      console.error('Upsert error:', upsertError)
      return NextResponse.json({ error: 'Failed to save creator profile' }, { status: 500 })
    }

    // Step 7: Trigger first scout run asynchronously
    if (creatorRow?.id) {
      triggerFirstScout(creatorRow.id).catch(console.error)
    }

    return NextResponse.json({ success: true })
  } catch (err) {
    console.error('Onboard error:', err)
    const message = err instanceof Error ? err.message : 'Failed to complete onboarding'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
