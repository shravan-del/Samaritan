'use client'

import { useState, useEffect, useCallback } from 'react'
import { supabase } from '@/lib/supabase'
import type { VideoIdea } from '@/lib/supabase'
import IdeaCard from '@/components/IdeaCard'

function thisMonday(): string {
  const now = new Date()
  const day = now.getDay()
  const diff = now.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(now.setDate(diff))
  return monday.toISOString().split('T')[0]
}

export default function IdeasPage() {
  const [ideas, setIdeas] = useState<VideoIdea[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('all')
  const [weekFilter, setWeekFilter] = useState(thisMonday())
  const [search, setSearch] = useState('')

  const loadIdeas = useCallback(async () => {
    const params = new URLSearchParams()
    if (statusFilter !== 'all') params.set('status', statusFilter)
    if (weekFilter) params.set('week', weekFilter)
    if (search) params.set('search', search)

    const res = await fetch(`/api/ideas?${params}`)
    const data = await res.json()
    setIdeas(data.ideas || [])
    setLoading(false)
  }, [statusFilter, weekFilter, search])

  useEffect(() => {
    loadIdeas()
  }, [loadIdeas])

  async function handleStatusChange(id: string, status: string) {
    await fetch('/api/ideas', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, status }),
    })
    await loadIdeas()
  }

  const weeks = [...new Set(ideas.map((i) => i.week_of).filter(Boolean))].sort().reverse() as string[]

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Video Ideas</h1>
        <p className="text-sm text-gray-400 mt-0.5">All your ranked ideas, sorted by viral potential</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="flex rounded-lg border border-gray-200 overflow-hidden">
          {['all', 'new', 'saved', 'used', 'dismissed'].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-2 text-xs font-medium capitalize transition-colors ${
                statusFilter === s
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-50'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {weeks.length > 1 && (
          <select
            value={weekFilter}
            onChange={(e) => setWeekFilter(e.target.value)}
            className="input w-auto text-xs"
          >
            {weeks.map((w) => (
              <option key={w} value={w}>
                Week of {new Date(w).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </option>
            ))}
          </select>
        )}

        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search ideas..."
          className="input w-auto text-xs flex-1 min-w-[160px]"
        />
      </div>

      {/* Ideas grid */}
      {loading ? (
        <div className="grid md:grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card animate-pulse">
              <div className="flex gap-2 mb-3">
                <div className="h-5 w-16 bg-gray-100 rounded-full" />
                <div className="h-5 w-12 bg-gray-100 rounded-full" />
              </div>
              <div className="h-4 bg-gray-100 rounded mb-2 w-3/4" />
              <div className="h-3 bg-gray-50 rounded w-full" />
            </div>
          ))}
        </div>
      ) : ideas.length === 0 ? (
        <div className="card text-center py-16">
          <div className="text-4xl mb-4">💡</div>
          <h3 className="text-base font-semibold text-gray-900 mb-2">No ideas yet</h3>
          <p className="text-sm text-gray-500">
            Your ideas will appear here after your first scout run. Click &quot;Run scout now&quot; on the overview page.
          </p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {ideas.map((idea) => (
            <IdeaCard key={idea.id} idea={idea} onStatusChange={handleStatusChange} />
          ))}
        </div>
      )}
    </div>
  )
}
