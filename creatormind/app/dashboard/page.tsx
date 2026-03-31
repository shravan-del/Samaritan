'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { supabase } from '@/lib/supabase'
import type { Creator, VideoIdea, WeeklyBrief } from '@/lib/supabase'
import IdeaCard from '@/components/IdeaCard'

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function greeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

function thisMonday(): string {
  const now = new Date()
  const day = now.getDay()
  const diff = now.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(now.setDate(diff))
  return monday.toISOString().split('T')[0]
}

export default function DashboardPage() {
  const [creator, setCreator] = useState<Creator | null>(null)
  const [brief, setBrief] = useState<WeeklyBrief | null>(null)
  const [topIdeas, setTopIdeas] = useState<VideoIdea[]>([])
  const [lastScout, setLastScout] = useState<string | null>(null)
  const [ideasThisWeek, setIdeasThisWeek] = useState(0)
  const [savedCount, setSavedCount] = useState(0)
  const [scouting, setScouting] = useState(false)
  const [scoutMsg, setScoutMsg] = useState('')

  const loadData = useCallback(async () => {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return

    const { data: creatorData } = await supabase
      .from('creators')
      .select('*')
      .eq('user_id', user.id)
      .single()

    if (creatorData) setCreator(creatorData as Creator)

    if (creatorData) {
      const weekOf = thisMonday()

      const [briefRes, ideasRes, scoutRes, savedRes] = await Promise.all([
        supabase
          .from('weekly_briefs')
          .select('*')
          .eq('creator_id', creatorData.id)
          .eq('week_of', weekOf)
          .single(),
        supabase
          .from('video_ideas')
          .select('*')
          .eq('creator_id', creatorData.id)
          .eq('week_of', weekOf)
          .order('viral_score', { ascending: false })
          .limit(3),
        supabase
          .from('scout_runs')
          .select('created_at')
          .eq('creator_id', creatorData.id)
          .order('created_at', { ascending: false })
          .limit(1),
        supabase
          .from('video_ideas')
          .select('id', { count: 'exact' })
          .eq('creator_id', creatorData.id)
          .eq('status', 'saved'),
      ])

      if (briefRes.data) setBrief(briefRes.data as WeeklyBrief)
      if (ideasRes.data) setTopIdeas(ideasRes.data as VideoIdea[])
      if (scoutRes.data?.[0]) setLastScout(scoutRes.data[0].created_at)
      if (ideasRes.data) setIdeasThisWeek(ideasRes.data.length)
      setSavedCount(savedRes.count || 0)
    }
  }, [])

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 60000)
    return () => clearInterval(interval)
  }, [loadData])

  async function handleScout() {
    setScouting(true)
    setScoutMsg('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const res = await fetch('/api/scout', {
        method: 'POST',
        headers: { ...(session?.access_token ? { 'Authorization': `Bearer ${session.access_token}` } : {}) },
      })
      const data = await res.json()
      if (res.ok) {
        setScoutMsg(`Generated ${data.ideasGenerated} ideas from ${data.trendsAnalyzed} trends`)
        await loadData()
      } else {
        setScoutMsg(data.error || 'Scout failed')
      }
    } catch {
      setScoutMsg('Something went wrong')
    } finally {
      setScouting(false)
      setTimeout(() => setScoutMsg(''), 5000)
    }
  }

  async function handleStatusChange(id: string, status: string) {
    await fetch('/api/ideas', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, status }),
    })
    await loadData()
  }

  const firstName = creator?.channel_name?.split(' ')[0] || 'there'

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {greeting()}, {firstName}
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">
            {creator?.channel_name} · {creator?.status === 'trial' ? 'Free trial' : 'Pro'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {scoutMsg && (
            <span className="text-sm text-green-700 bg-green-50 px-3 py-1.5 rounded-lg">
              {scoutMsg}
            </span>
          )}
          <button
            onClick={handleScout}
            disabled={scouting}
            className="btn-secondary flex items-center gap-2 disabled:opacity-50"
          >
            {scouting ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin" />
                Scouting...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                Run scout now
              </>
            )}
          </button>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="stat-card">
          <div className="text-2xl font-bold text-gray-900">{ideasThisWeek}</div>
          <div className="text-xs text-gray-400 mt-0.5">Ideas this week</div>
        </div>
        <div className="stat-card">
          <div className="text-2xl font-bold text-gray-900">{savedCount}</div>
          <div className="text-xs text-gray-400 mt-0.5">Ideas saved</div>
        </div>
        <div className="stat-card">
          <div className="text-sm font-semibold text-gray-700">
            {lastScout ? timeAgo(lastScout) : 'Not yet'}
          </div>
          <div className="text-xs text-gray-400 mt-0.5">Last scout run</div>
        </div>
        <div className="stat-card">
          <div>
            <span className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full ${
              creator?.status === 'active'
                ? 'bg-green-100 text-green-700'
                : creator?.status === 'cancelled'
                ? 'bg-red-100 text-red-700'
                : 'bg-indigo-100 text-indigo-700'
            }`}>
              {creator?.status === 'active' ? 'Pro' : creator?.status === 'cancelled' ? 'Cancelled' : 'Trial'}
            </span>
          </div>
          <div className="text-xs text-gray-400 mt-0.5">Account status</div>
        </div>
      </div>

      {/* Weekly brief */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900">This week&apos;s brief</h2>
          {brief && (
            <Link href="/dashboard/calendar" className="text-sm text-indigo-600 hover:text-indigo-700">
              View full calendar →
            </Link>
          )}
        </div>

        {brief && brief.summary ? (
          <div className="space-y-4">
            <p className="text-sm text-gray-700 leading-relaxed">{brief.summary}</p>
            {brief.top_trend && (
              <div className="bg-amber-50 border border-amber-100 rounded-lg p-3">
                <div className="text-xs font-semibold text-amber-600 mb-1">TOP TREND</div>
                <p className="text-sm text-amber-900">{brief.top_trend}</p>
              </div>
            )}
            {brief.platform_insight && (
              <p className="text-sm text-gray-500 italic border-l-2 border-indigo-200 pl-3">
                {brief.platform_insight}
              </p>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-3 text-sm text-gray-400 py-4">
            <div className="w-4 h-4 border-2 border-gray-200 border-t-gray-400 rounded-full animate-spin" />
            {creator?.profile_built
              ? "Your first brief is being generated..."
              : "Complete onboarding to generate your first brief."}
          </div>
        )}
      </div>

      {/* Top ideas */}
      {topIdeas.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900">Your best ideas this week</h2>
            <Link href="/dashboard/ideas" className="text-sm text-indigo-600 hover:text-indigo-700">
              See all 10 ideas →
            </Link>
          </div>
          <div className="grid md:grid-cols-3 gap-4">
            {topIdeas.map((idea) => (
              <IdeaCard key={idea.id} idea={idea} onStatusChange={handleStatusChange} />
            ))}
          </div>
        </div>
      )}

      {/* Format to steal */}
      {brief?.format_to_steal && (
        <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-5">
          <div className="text-xs font-semibold text-indigo-500 uppercase tracking-wide mb-2">
            Format to test this week
          </div>
          <p className="text-sm text-indigo-900 leading-relaxed">{brief.format_to_steal}</p>
          <p className="text-xs text-indigo-400 mt-2">
            This format is trending on short-form. Here&apos;s how to adapt it for YouTube.
          </p>
        </div>
      )}

      {/* Empty state */}
      {topIdeas.length === 0 && creator?.profile_built && (
        <div className="card text-center py-12">
          <div className="text-4xl mb-4">🧠</div>
          <h3 className="text-base font-semibold text-gray-900 mb-2">
            Your CreatorMind is warming up
          </h3>
          <p className="text-sm text-gray-500 mb-5">
            Your first scout run is in progress. Ideas will appear here shortly.
          </p>
          <button onClick={handleScout} disabled={scouting} className="btn-primary disabled:opacity-50">
            {scouting ? 'Scouting...' : 'Run scout now'}
          </button>
        </div>
      )}
    </div>
  )
}
