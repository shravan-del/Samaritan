export const dynamic = 'force-dynamic'

import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase'
import { getAuthUser } from '@/lib/auth'

function thisMonday(): string {
  const now = new Date()
  const day = now.getDay()
  const diff = now.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(now.setDate(diff))
  return monday.toISOString().split('T')[0]
}

export async function GET(req: Request) {
  try {
    const user = await getAuthUser(req)
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const admin = supabaseAdmin()
    const weekOf = thisMonday()

    const { data: creator } = await admin
      .from('creators')
      .select('id')
      .eq('user_id', user.id)
      .single()

    if (!creator) {
      return NextResponse.json({ error: 'Creator not found' }, { status: 404 })
    }

    const { data: brief } = await admin
      .from('weekly_briefs')
      .select('*')
      .eq('creator_id', creator.id)
      .eq('week_of', weekOf)
      .single()

    const { data: topIdeas } = await admin
      .from('video_ideas')
      .select('*')
      .eq('creator_id', creator.id)
      .eq('week_of', weekOf)
      .order('viral_score', { ascending: false })
      .limit(5)

    return NextResponse.json({ brief: brief || null, topIdeas: topIdeas || [] })
  } catch (err) {
    console.error('Brief GET error:', err)
    return NextResponse.json({ error: 'Failed to fetch brief' }, { status: 500 })
  }
}
