'use client'

import type { WeeklyBrief, VideoIdea } from '@/lib/supabase'

interface BriefSectionProps {
  brief: WeeklyBrief
  topIdeas: VideoIdea[]
}

export default function BriefSection({ brief, topIdeas }: BriefSectionProps) {
  function formatDate(dateStr: string) {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Weekly Brief</h2>
          <p className="text-sm text-gray-400 mt-0.5">Week of {formatDate(brief.week_of)}</p>
        </div>
      </div>

      {/* Summary */}
      {brief.summary && (
        <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-5">
          <p className="text-sm text-indigo-900 leading-relaxed">{brief.summary}</p>
        </div>
      )}

      {/* Top Trend */}
      {brief.top_trend && (
        <div className="stat-card">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
            Top Trend This Week
          </p>
          <p className="text-sm text-gray-800 leading-relaxed">{brief.top_trend}</p>
        </div>
      )}

      {/* Top Ideas */}
      {topIdeas.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Top Ideas</h3>
          <div className="space-y-3">
            {topIdeas.slice(0, 3).map((idea) => (
              <div key={idea.id} className="bg-white border border-gray-100 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className={`text-xs font-mono font-medium px-2 py-0.5 rounded-full ${
                    idea.viral_score >= 80
                      ? 'bg-green-100 text-green-700'
                      : idea.viral_score >= 60
                      ? 'bg-amber-100 text-amber-700'
                      : 'bg-gray-100 text-gray-600'
                  }`}>
                    {idea.viral_score}/100
                  </span>
                  {idea.format && (
                    <span className="text-xs text-gray-500">{idea.format}</span>
                  )}
                </div>
                <p className="text-sm font-medium text-gray-900">{idea.title}</p>
                <p className="text-xs text-gray-500 italic mt-1">{idea.hook}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Format to steal */}
      {brief.format_to_steal && (
        <div className="bg-indigo-50 rounded-xl p-5">
          <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wide mb-1">
            Format to test this week
          </p>
          <p className="text-sm text-indigo-900 leading-relaxed">{brief.format_to_steal}</p>
        </div>
      )}

      {/* Platform insight */}
      {brief.platform_insight && (
        <div className="border-l-4 border-indigo-500 pl-4">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
            Platform Insight
          </p>
          <p className="text-sm text-gray-700 leading-relaxed">{brief.platform_insight}</p>
        </div>
      )}
    </div>
  )
}
