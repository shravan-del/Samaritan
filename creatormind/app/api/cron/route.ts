import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase'
import { scoutTrends } from '@/lib/scout'
import { generateVideoIdeas, generateWeeklyBrief } from '@/lib/anthropic'
import { sendWeeklyBrief } from '@/lib/email'

function thisMonday(): string {
  const now = new Date()
  const day = now.getDay()
  const diff = now.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(now.setDate(diff))
  return monday.toISOString().split('T')[0]
}

function isMonday(): boolean {
  return new Date().getDay() === 1
}

export async function POST(req: Request) {
  const authHeader = req.headers.get('authorization')

  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const admin = supabaseAdmin()
  const weekOf = thisMonday()
  const monday = isMonday()

  // Get all active/trial creators with built profiles
  const { data: creators, error } = await admin
    .from('creators')
    .select('*')
    .in('status', ['trial', 'active'])
    .eq('profile_built', true)

  if (error) {
    return NextResponse.json({ error: 'Failed to fetch creators' }, { status: 500 })
  }

  let processed = 0
  let errors = 0
  let totalIdeas = 0

  for (const creator of creators || []) {
    try {
      // 1. Run scout
      const trends = await scoutTrends(creator.niche || '', creator.content_pillars || [])
      const result = await generateVideoIdeas({ creator, trends, weekOf })

      // Dedup check
      const cutoff = new Date()
      cutoff.setDate(cutoff.getDate() - 14)
      const { data: existingIdeas } = await admin
        .from('video_ideas')
        .select('title')
        .eq('creator_id', creator.id)
        .gte('created_at', cutoff.toISOString())

      const existingTitles = new Set((existingIdeas || []).map((i: { title: string }) => i.title.toLowerCase()))
      const newIdeas = result.ideas.filter((idea) => !existingTitles.has(idea.title.toLowerCase()))

      if (newIdeas.length > 0) {
        await admin.from('video_ideas').insert(
          newIdeas.map((idea) => ({
            creator_id: creator.id,
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
        )
        totalIdeas += newIdeas.length
      }

      // Replace pivots
      await admin.from('pivot_opportunities').delete().eq('creator_id', creator.id).eq('week_of', weekOf)
      if (result.pivots.length > 0) {
        await admin.from('pivot_opportunities').insert(
          result.pivots.map((p) => ({
            creator_id: creator.id,
            niche: p.niche,
            rationale: p.rationale,
            example_channels: p.exampleChannels,
            difficulty: p.difficulty,
            revenue_potential: p.revenuePotential,
            week_of: weekOf,
          }))
        )
      }

      await admin.from('weekly_briefs').upsert(
        {
          creator_id: creator.id,
          week_of: weekOf,
          summary: '',
          format_to_steal: result.formatToSteal,
          platform_insight: result.platformInsight,
          calendar: [],
        },
        { onConflict: 'creator_id,week_of' }
      )

      await admin.from('scout_runs').insert({
        creator_id: creator.id,
        sources_checked: trends.length,
        ideas_generated: newIdeas.length,
      })

      // 2. If Monday, generate brief and send email
      if (monday) {
        const { data: topIdeas } = await admin
          .from('video_ideas')
          .select('*')
          .eq('creator_id', creator.id)
          .eq('week_of', weekOf)
          .order('viral_score', { ascending: false })
          .limit(10)

        const { data: pivots } = await admin
          .from('pivot_opportunities')
          .select('*')
          .eq('creator_id', creator.id)
          .eq('week_of', weekOf)
          .limit(3)

        const { data: existingBrief } = await admin
          .from('weekly_briefs')
          .select('id, email_sent')
          .eq('creator_id', creator.id)
          .eq('week_of', weekOf)
          .single()

        if (!existingBrief?.email_sent) {
          const briefResult = await generateWeeklyBrief({
            creator,
            topIdeas: topIdeas || [],
            pivots: pivots || [],
            formatToSteal: result.formatToSteal,
            platformInsight: result.platformInsight,
          })

          const { data: savedBrief } = await admin
            .from('weekly_briefs')
            .upsert(
              {
                creator_id: creator.id,
                week_of: weekOf,
                summary: briefResult.summary,
                top_trend: briefResult.topTrend,
                calendar: briefResult.calendar,
                format_to_steal: result.formatToSteal,
                platform_insight: result.platformInsight,
                email_sent: false,
              },
              { onConflict: 'creator_id,week_of' }
            )
            .select('id')
            .single()

          // Get user email
          const { data: userAuth } = await admin.auth.admin.getUserById(creator.user_id)
          const userEmail = userAuth?.user?.email

          if (userEmail && savedBrief) {
            const briefForEmail = {
              id: savedBrief.id,
              creator_id: creator.id,
              week_of: weekOf,
              summary: briefResult.summary,
              top_trend: briefResult.topTrend,
              calendar: briefResult.calendar,
              format_to_steal: result.formatToSteal,
              platform_insight: result.platformInsight,
              email_sent: false,
              created_at: new Date().toISOString(),
            }

            await sendWeeklyBrief({
              to: userEmail,
              creatorName: creator.channel_name?.split(' ')[0] || 'Creator',
              channelName: creator.channel_name || 'Your Channel',
              brief: briefForEmail,
              topIdeas: (topIdeas || []).slice(0, 3),
            })

            await admin
              .from('weekly_briefs')
              .update({ email_sent: true })
              .eq('id', savedBrief.id)
          }
        }
      }

      processed++
    } catch (err) {
      console.error(`Cron error for creator ${creator.id}:`, err)
      await admin.from('scout_runs').insert({
        creator_id: creator.id,
        sources_checked: 0,
        ideas_generated: 0,
        error: err instanceof Error ? err.message : 'Unknown error',
      })
      errors++
    }
  }

  return NextResponse.json({ processed, errors, totalIdeas })
}
