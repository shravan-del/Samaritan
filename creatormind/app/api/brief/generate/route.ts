export const dynamic = 'force-dynamic'

import { NextResponse } from 'next/server'
import { createServerClient, supabaseAdmin } from '@/lib/supabase'
import { generateWeeklyBrief } from '@/lib/anthropic'
import { sendWeeklyBrief } from '@/lib/email'

function thisMonday(): string {
  const now = new Date()
  const day = now.getDay()
  const diff = now.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(now.setDate(diff))
  return monday.toISOString().split('T')[0]
}

export async function POST(req: Request) {
  const authHeader = req.headers.get('authorization')
  const isCron = authHeader === `Bearer ${process.env.CRON_SECRET}`

  let userId: string | null = null
  let creatorId: string | null = null

  if (!isCron) {
    const supabase = await createServerClient()
    const { data: { user }, error: authError } = await supabase.auth.getUser()

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    userId = user.id
  }

  const body = await req.json().catch(() => ({}))
  const force = body?.force === true

  const admin = supabaseAdmin()
  const weekOf = thisMonday()

  try {
    // Get creator
    let creator: Record<string, unknown> | null = null

    if (userId) {
      const { data } = await admin
        .from('creators')
        .select('*')
        .eq('user_id', userId)
        .single()
      creator = data
    } else if (body?.creatorId) {
      const { data } = await admin
        .from('creators')
        .select('*')
        .eq('id', body.creatorId)
        .single()
      creator = data
    }

    if (!creator) {
      return NextResponse.json({ error: 'Creator not found' }, { status: 404 })
    }

    creatorId = creator.id as string

    // Check if brief already exists
    const { data: existingBrief } = await admin
      .from('weekly_briefs')
      .select('id, email_sent')
      .eq('creator_id', creatorId)
      .eq('week_of', weekOf)
      .not('summary', 'eq', '')
      .single()

    if (existingBrief && !force) {
      return NextResponse.json({ briefId: existingBrief.id })
    }

    // Get top 10 ideas for this week
    const { data: topIdeas } = await admin
      .from('video_ideas')
      .select('*')
      .eq('creator_id', creatorId)
      .eq('week_of', weekOf)
      .order('viral_score', { ascending: false })
      .limit(10)

    // Get pivots
    const { data: pivots } = await admin
      .from('pivot_opportunities')
      .select('*')
      .eq('creator_id', creatorId)
      .eq('week_of', weekOf)
      .limit(3)

    // Get format/insight from existing brief meta
    const { data: briefMeta } = await admin
      .from('weekly_briefs')
      .select('format_to_steal, platform_insight')
      .eq('creator_id', creatorId)
      .eq('week_of', weekOf)
      .single()

    const formatToSteal = briefMeta?.format_to_steal || ''
    const platformInsight = briefMeta?.platform_insight || ''

    // Generate brief
    const briefResult = await generateWeeklyBrief({
      creator: creator as Parameters<typeof generateWeeklyBrief>[0]['creator'],
      topIdeas: topIdeas || [],
      pivots: pivots || [],
      formatToSteal,
      platformInsight,
    })

    // Upsert weekly brief
    const { data: upsertedBrief, error: upsertError } = await admin
      .from('weekly_briefs')
      .upsert(
        {
          creator_id: creatorId,
          week_of: weekOf,
          summary: briefResult.summary,
          top_trend: briefResult.topTrend,
          calendar: briefResult.calendar,
          format_to_steal: formatToSteal,
          platform_insight: platformInsight,
          email_sent: existingBrief?.email_sent || false,
        },
        { onConflict: 'creator_id,week_of' }
      )
      .select('id')
      .single()

    if (upsertError) {
      console.error('Brief upsert error:', upsertError)
      return NextResponse.json({ error: 'Failed to save brief' }, { status: 500 })
    }

    // Send email if not a force-regeneration (or if it's a cron run and email hasn't been sent)
    if (!force && !existingBrief?.email_sent) {
      try {
        const { data: userAuth } = await admin.auth.admin.getUserById(creator.user_id as string)
        const userEmail = userAuth?.user?.email

        if (userEmail) {
          const briefForEmail = {
            id: upsertedBrief!.id,
            creator_id: creatorId!,
            week_of: weekOf,
            summary: briefResult.summary,
            top_trend: briefResult.topTrend,
            calendar: briefResult.calendar,
            format_to_steal: formatToSteal,
            platform_insight: platformInsight,
            email_sent: false,
            created_at: new Date().toISOString(),
          }

          await sendWeeklyBrief({
            to: userEmail,
            creatorName: (creator.channel_name as string)?.split(' ')[0] || 'Creator',
            channelName: creator.channel_name as string || 'Your Channel',
            brief: briefForEmail,
            topIdeas: (topIdeas || []).slice(0, 3),
          })

          await admin
            .from('weekly_briefs')
            .update({ email_sent: true })
            .eq('id', upsertedBrief!.id)
        }
      } catch (emailErr) {
        console.error('Email send error (non-fatal):', emailErr)
      }
    }

    return NextResponse.json({ briefId: upsertedBrief?.id })
  } catch (err) {
    console.error('Brief generate error:', err)
    const message = err instanceof Error ? err.message : 'Failed to generate brief'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
