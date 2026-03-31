export const dynamic = 'force-dynamic'

import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase'
import { getAuthUser } from '@/lib/auth'
import { scoutTrends } from '@/lib/scout'
import { generateVideoIdeas } from '@/lib/anthropic'

function thisMonday(): string {
  const now = new Date()
  const day = now.getDay()
  const diff = now.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(now.setDate(diff))
  return monday.toISOString().split('T')[0]
}

async function runScoutForCreator(creatorId: string) {
  const admin = supabaseAdmin()
  const weekOf = thisMonday()

  const { data: creator, error: creatorError } = await admin
    .from('creators')
    .select('*')
    .eq('id', creatorId)
    .single()

  if (creatorError || !creator) throw new Error('Creator not found')
  if (!creator.profile_built) throw new Error('Creator profile not yet built')

  const trends = await scoutTrends(creator.niche || '', creator.content_pillars || [])
  const result = await generateVideoIdeas({ creator, trends, weekOf })

  // Deduplicate: check for similar titles in last 14 days
  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() - 14)

  const { data: existingIdeas } = await admin
    .from('video_ideas')
    .select('title')
    .eq('creator_id', creatorId)
    .gte('created_at', cutoff.toISOString())

  const existingTitles = new Set((existingIdeas || []).map((i: { title: string }) => i.title.toLowerCase()))

  const newIdeas = result.ideas.filter(
    (idea) => !existingTitles.has(idea.title.toLowerCase())
  )

  let ideasGenerated = 0

  if (newIdeas.length > 0) {
    const ideasToInsert = newIdeas.map((idea) => ({
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

    const { error: ideasError } = await admin.from('video_ideas').insert(ideasToInsert)
    if (ideasError) console.error('Ideas insert error:', ideasError)
    else ideasGenerated = ideasToInsert.length
  }

  // Replace this week's pivots
  await admin
    .from('pivot_opportunities')
    .delete()
    .eq('creator_id', creatorId)
    .eq('week_of', weekOf)

  if (result.pivots.length > 0) {
    await admin.from('pivot_opportunities').insert(
      result.pivots.map((p) => ({
        creator_id: creatorId,
        niche: p.niche,
        rationale: p.rationale,
        example_channels: p.exampleChannels,
        difficulty: p.difficulty,
        revenue_potential: p.revenuePotential,
        week_of: weekOf,
      }))
    )
  }

  // Update weekly brief meta
  await admin.from('weekly_briefs').upsert(
    {
      creator_id: creatorId,
      week_of: weekOf,
      summary: '',
      format_to_steal: result.formatToSteal,
      platform_insight: result.platformInsight,
      calendar: [],
    },
    { onConflict: 'creator_id,week_of' }
  )

  // Log the scout run
  await admin.from('scout_runs').insert({
    creator_id: creatorId,
    sources_checked: trends.length,
    ideas_generated: ideasGenerated,
  })

  return {
    ideasGenerated,
    pivotsGenerated: result.pivots.length,
    trendsAnalyzed: trends.length,
  }
}

export async function POST(req: Request) {
  // Allow cron secret OR authenticated user
  const authHeader = req.headers.get('authorization')
  const isCron = authHeader === `Bearer ${process.env.CRON_SECRET}`

  let creatorId: string | null = null

  if (!isCron) {
    const user = await getAuthUser(req)

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const admin = supabaseAdmin()
    const { data: creator } = await admin
      .from('creators')
      .select('id, profile_built')
      .eq('user_id', user.id)
      .single()

    if (!creator) {
      return NextResponse.json({ error: 'Creator profile not found. Complete onboarding first.' }, { status: 400 })
    }

    if (!creator.profile_built) {
      return NextResponse.json({ error: 'Profile not yet built. Please complete onboarding.' }, { status: 400 })
    }

    creatorId = creator.id
  }

  try {
    if (creatorId) {
      const result = await runScoutForCreator(creatorId)
      return NextResponse.json(result)
    }

    return NextResponse.json({ error: 'No creator specified' }, { status: 400 })
  } catch (err) {
    console.error('Scout error:', err)
    const message = err instanceof Error ? err.message : 'Scout run failed'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}

