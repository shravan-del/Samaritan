'use client'

import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'
import type { PivotOpportunity } from '@/lib/supabase'
import PivotCard from '@/components/PivotCard'

function thisMonday(): string {
  const now = new Date()
  const day = now.getDay()
  const diff = now.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(now.setDate(diff))
  return monday.toISOString().split('T')[0]
}

function formatWeek(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export default function PivotsPage() {
  const [pivots, setPivots] = useState<PivotOpportunity[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return

      const { data: creator } = await supabase
        .from('creators')
        .select('id')
        .eq('user_id', user.id)
        .single()

      if (!creator) { setLoading(false); return }

      const { data } = await supabase
        .from('pivot_opportunities')
        .select('*')
        .eq('creator_id', creator.id)
        .order('created_at', { ascending: false })

      setPivots((data || []) as PivotOpportunity[])
      setLoading(false)
    }
    load()
  }, [])

  const currentWeek = thisMonday()
  const thisPivots = pivots.filter((p) => p.week_of === currentWeek)
  const previousPivots = pivots.filter((p) => p.week_of !== currentWeek)

  const previousWeeks = [...new Set(previousPivots.map((p) => p.week_of))].sort().reverse() as string[]
  const [openWeeks, setOpenWeeks] = useState<Set<string>>(new Set())

  function toggleWeek(week: string) {
    setOpenWeeks((prev) => {
      const next = new Set(prev)
      next.has(week) ? next.delete(week) : next.add(week)
      return next
    })
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Pivot Opportunities</h1>
        <p className="text-sm text-gray-400 mt-0.5">
          Adjacent niches you could expand into this week
        </p>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card animate-pulse h-40" />
          ))}
        </div>
      ) : thisPivots.length > 0 ? (
        <>
          <div className="space-y-4">
            {thisPivots.map((pivot) => (
              <PivotCard key={pivot.id} pivot={pivot} />
            ))}
          </div>

          {/* Previous weeks */}
          {previousWeeks.length > 0 && (
            <div className="mt-8">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
                Previous weeks
              </h2>
              <div className="space-y-2">
                {previousWeeks.map((week) => {
                  const weekPivots = previousPivots.filter((p) => p.week_of === week)
                  const isOpen = openWeeks.has(week)
                  return (
                    <div key={week} className="border border-gray-100 rounded-xl overflow-hidden">
                      <button
                        onClick={() => toggleWeek(week)}
                        className="w-full flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors"
                      >
                        <span className="text-sm font-medium text-gray-700">
                          Week of {formatWeek(week)}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400">{weekPivots.length} pivots</span>
                          <svg
                            className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                            fill="none" viewBox="0 0 24 24" stroke="currentColor"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                      </button>
                      {isOpen && (
                        <div className="px-5 pb-5 space-y-4 border-t border-gray-50 pt-4">
                          {weekPivots.map((pivot) => (
                            <PivotCard key={pivot.id} pivot={pivot} />
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="card text-center py-16">
          <div className="text-4xl mb-4">🧭</div>
          <h3 className="text-base font-semibold text-gray-900 mb-2">No pivot opportunities yet</h3>
          <p className="text-sm text-gray-500">
            Run a scout from the overview page to discover adjacent niches you could expand into.
          </p>
        </div>
      )}
    </div>
  )
}
