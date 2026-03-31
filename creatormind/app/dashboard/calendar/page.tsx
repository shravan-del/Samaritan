'use client'

import { useState, useEffect } from 'react'
import type { WeeklyBrief } from '@/lib/supabase'
import CalendarView from '@/components/CalendarView'

export default function CalendarPage() {
  const [brief, setBrief] = useState<WeeklyBrief | null>(null)
  const [loading, setLoading] = useState(true)
  const [regenerating, setRegenerating] = useState(false)
  const [message, setMessage] = useState('')

  async function loadBrief() {
    const res = await fetch('/api/brief')
    const data = await res.json()
    if (data.brief) setBrief(data.brief as WeeklyBrief)
    setLoading(false)
  }

  useEffect(() => {
    loadBrief()
  }, [])

  async function handleRegenerate() {
    setRegenerating(true)
    setMessage('')
    try {
      const res = await fetch('/api/brief/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: true }),
      })
      if (res.ok) {
        setMessage('Calendar regenerated!')
        await loadBrief()
      } else {
        setMessage('Failed to regenerate. Try again.')
      }
    } catch {
      setMessage('Something went wrong.')
    } finally {
      setRegenerating(false)
      setTimeout(() => setMessage(''), 3000)
    }
  }

  function handlePrint() {
    window.print()
  }

  function formatDate(dateStr: string) {
    return new Date(dateStr).toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
    })
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Content Calendar</h1>
          {brief && (
            <p className="text-sm text-gray-400 mt-0.5">
              Week of {formatDate(brief.week_of)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {message && (
            <span className="text-sm text-green-700 bg-green-50 px-3 py-1.5 rounded-lg">
              {message}
            </span>
          )}
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="btn-secondary text-sm disabled:opacity-50"
          >
            {regenerating ? 'Regenerating...' : 'Regenerate'}
          </button>
          <button onClick={handlePrint} className="btn-ghost text-sm">
            Print
          </button>
        </div>
      </div>

      {loading ? (
        <div className="card animate-pulse h-48" />
      ) : brief?.calendar && brief.calendar.length > 0 ? (
        <>
          {/* Calendar grid */}
          <div className="card overflow-hidden">
            <CalendarView calendar={brief.calendar} />
          </div>

          {/* Hooks section */}
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">This week&apos;s hooks</h2>
            <div className="space-y-4">
              {brief.calendar.map((day) => (
                <div key={day.day} className="flex gap-4">
                  <div className="text-xs font-mono text-gray-400 w-12 flex-shrink-0 pt-0.5">
                    {day.day.slice(0, 3).toUpperCase()}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-800 mb-1">{day.title}</div>
                    <div className="text-sm text-gray-500 italic leading-relaxed bg-gray-50 px-3 py-2 rounded-lg">
                      &ldquo;{day.hook}&rdquo;
                    </div>
                    {day.timing_reason && (
                      <div className="text-xs text-indigo-500 mt-1.5">
                        Why {day.day}: {day.timing_reason}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : (
        <div className="card text-center py-16">
          <div className="text-4xl mb-4">📅</div>
          <h3 className="text-base font-semibold text-gray-900 mb-2">No calendar yet</h3>
          <p className="text-sm text-gray-500 mb-5">
            Run a scout first to generate ideas, then we&apos;ll build your calendar.
          </p>
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="btn-primary disabled:opacity-50"
          >
            {regenerating ? 'Generating...' : 'Generate calendar'}
          </button>
        </div>
      )}
    </div>
  )
}
