'use client'

import { useState } from 'react'
import type { VideoIdea } from '@/lib/supabase'

function ScoreBadge({ score }: { score: number }) {
  const cls = score >= 80 ? 'score-high' : score >= 60 ? 'score-mid' : 'score-low'
  return <span className={cls}>{score}/100</span>
}

function sourceLabel(source: string | null) {
  if (!source) return null
  if (source.toLowerCase().includes('youtube') || source.toLowerCase().includes('trending')) return 'YouTube'
  if (source.toLowerCase().includes('reddit')) return 'Reddit'
  return 'Web'
}

interface IdeaCardProps {
  idea: VideoIdea
  onStatusChange: (id: string, status: string) => void
}

export default function IdeaCard({ idea, onStatusChange }: IdeaCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [loading, setLoading] = useState(false)

  const status = idea.status
  if (status === 'dismissed') return null

  const source = sourceLabel(idea.trend_source)
  const isMuted = status === 'used'

  async function handleStatus(status: string) {
    setLoading(true)
    await onStatusChange(idea.id, status)
    setLoading(false)
  }

  return (
    <div
      className={`card transition-all duration-150 ${isMuted ? 'opacity-60' : ''}`}
    >
      {/* Top row */}
      <div className="flex items-center gap-2 flex-wrap">
        <ScoreBadge score={idea.viral_score} />
        {idea.format && (
          <span className="bg-gray-100 text-gray-600 text-xs font-medium px-2 py-0.5 rounded-full">
            {idea.format}
          </span>
        )}
        {source && (
          <span className="bg-indigo-50 text-indigo-600 text-xs font-medium px-2 py-0.5 rounded-full">
            {source}
          </span>
        )}
        {status === 'saved' && (
          <span className="bg-green-100 text-green-700 text-xs font-medium px-2 py-0.5 rounded-full ml-auto">
            Saved ✓
          </span>
        )}
      </div>

      {/* Title */}
      <h3 className="text-base font-semibold text-gray-900 mt-3 leading-snug">
        {idea.title}
      </h3>

      {/* Hook */}
      <p className="text-sm text-gray-500 italic mt-1.5">
        Hook: {idea.hook}
      </p>

      {/* Expandable section */}
      {(idea.thumbnail_concept || idea.description || idea.why_now || idea.estimated_views) && (
        <div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-indigo-600 hover:text-indigo-700 mt-3 font-medium transition-colors"
          >
            {expanded ? 'Show less ↑' : 'Show more ↓'}
          </button>

          {expanded && (
            <div className="mt-3 space-y-2.5 text-sm text-gray-600">
              {idea.description && (
                <p className="leading-relaxed">{idea.description}</p>
              )}
              {idea.thumbnail_concept && (
                <div className="bg-gray-50 rounded-lg p-3">
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide block mb-1">
                    Thumbnail
                  </span>
                  {idea.thumbnail_concept}
                </div>
              )}
              {idea.why_now && (
                <div className="bg-indigo-50 rounded-lg p-3">
                  <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wide block mb-1">
                    Why now
                  </span>
                  <span className="text-indigo-800">{idea.why_now}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Bottom row */}
      <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-50">
        <span className="text-xs text-gray-400">
          {idea.estimated_views && `~${idea.estimated_views} est. views`}
        </span>
        <div className="flex items-center gap-2">
          {status !== 'saved' && status !== 'used' && (
            <button
              onClick={() => handleStatus('saved')}
              disabled={loading}
              className="text-xs border border-indigo-200 text-indigo-600 hover:bg-indigo-50 px-3 py-1.5 rounded-lg font-medium transition-all disabled:opacity-50"
            >
              Save
            </button>
          )}
          {status !== 'used' && (
            <button
              onClick={() => handleStatus('used')}
              disabled={loading}
              className="text-xs text-green-600 hover:bg-green-50 px-3 py-1.5 rounded-lg font-medium transition-all disabled:opacity-50"
            >
              Mark used
            </button>
          )}
          <button
            onClick={() => handleStatus('dismissed')}
            disabled={loading}
            className="btn-ghost text-xs py-1.5"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  )
}
