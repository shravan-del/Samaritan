'use client'

import type { PivotOpportunity } from '@/lib/supabase'

const DIFFICULTY_STYLES = {
  easy: 'bg-green-100 text-green-700',
  medium: 'bg-amber-100 text-amber-700',
  hard: 'bg-red-100 text-red-700',
}

interface PivotCardProps {
  pivot: PivotOpportunity
}

export default function PivotCard({ pivot }: PivotCardProps) {
  const difficultyStyle = DIFFICULTY_STYLES[pivot.difficulty] || DIFFICULTY_STYLES.medium

  return (
    <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
      {/* Accent bar */}
      <div className="h-1 bg-indigo-500 w-full" />

      <div className="p-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <h3 className="text-lg font-bold text-gray-900 leading-tight">{pivot.niche}</h3>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full capitalize ${difficultyStyle}`}>
              {pivot.difficulty}
            </span>
          </div>
        </div>

        {/* Revenue potential */}
        {pivot.revenue_potential && (
          <p className="text-sm text-gray-500 mb-3">
            <span className="font-medium text-gray-700">Revenue potential:</span> {pivot.revenue_potential}
          </p>
        )}

        {/* Rationale */}
        <p className="text-sm text-gray-600 leading-relaxed mb-4">{pivot.rationale}</p>

        {/* Example channels */}
        {pivot.example_channels && pivot.example_channels.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
              Example channels to study:
            </p>
            <div className="flex flex-wrap gap-2">
              {pivot.example_channels.map((channel) => (
                <span
                  key={channel}
                  className="bg-gray-100 text-gray-600 text-xs px-2.5 py-1 rounded-lg"
                >
                  {channel}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* CTA */}
        <button className="btn-ghost text-sm text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50 px-0">
          Looks interesting →
        </button>
      </div>
    </div>
  )
}
