export const dynamic = 'force-dynamic'

import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase'
import { getAuthUser } from '@/lib/auth'

export async function GET(req: Request) {
  try {
    const user = await getAuthUser(req)
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const url = new URL(req.url)
    const status = url.searchParams.get('status')
    const week = url.searchParams.get('week')
    const search = url.searchParams.get('search')

    const admin = supabaseAdmin()

    const { data: creator } = await admin
      .from('creators')
      .select('id')
      .eq('user_id', user.id)
      .single()

    if (!creator) {
      return NextResponse.json({ error: 'Creator not found' }, { status: 404 })
    }

    let query = admin
      .from('video_ideas')
      .select('*')
      .eq('creator_id', creator.id)
      .order('viral_score', { ascending: false })

    if (status && status !== 'all') {
      query = query.eq('status', status)
    }

    if (week) {
      query = query.eq('week_of', week)
    }

    if (search) {
      query = query.ilike('title', `%${search}%`)
    }

    const { data: ideas, error } = await query

    if (error) {
      return NextResponse.json({ error: 'Failed to fetch ideas' }, { status: 500 })
    }

    return NextResponse.json({ ideas: ideas || [] })
  } catch (err) {
    console.error('Ideas GET error:', err)
    return NextResponse.json({ error: 'Failed to fetch ideas' }, { status: 500 })
  }
}

export async function PATCH(req: Request) {
  try {
    const user = await getAuthUser(req)
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await req.json()
    const { id, status } = body

    if (!id || !status) {
      return NextResponse.json({ error: 'id and status are required' }, { status: 400 })
    }

    const validStatuses = ['saved', 'dismissed', 'used', 'new']
    if (!validStatuses.includes(status)) {
      return NextResponse.json({ error: 'Invalid status' }, { status: 400 })
    }

    const admin = supabaseAdmin()

    // Verify the idea belongs to this creator
    const { data: creator } = await admin
      .from('creators')
      .select('id')
      .eq('user_id', user.id)
      .single()

    if (!creator) {
      return NextResponse.json({ error: 'Creator not found' }, { status: 404 })
    }

    const { data: idea } = await admin
      .from('video_ideas')
      .select('id')
      .eq('id', id)
      .eq('creator_id', creator.id)
      .single()

    if (!idea) {
      return NextResponse.json({ error: 'Idea not found or access denied' }, { status: 404 })
    }

    const { error: updateError } = await admin
      .from('video_ideas')
      .update({ status })
      .eq('id', id)

    if (updateError) {
      return NextResponse.json({ error: 'Failed to update idea status' }, { status: 500 })
    }

    return NextResponse.json({ success: true })
  } catch (err) {
    console.error('Ideas PATCH error:', err)
    return NextResponse.json({ error: 'Failed to update idea' }, { status: 500 })
  }
}
