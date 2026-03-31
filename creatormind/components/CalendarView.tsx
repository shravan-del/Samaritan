'use client'

import type { CalendarDay } from '@/lib/supabase'

const DAY_ABBREV: Record<string, string> = {
  Monday: 'MON',
  Tuesday: 'TUE',
  Wednesday: 'WED',
  Thursday: 'THU',
  Friday: 'FRI',
  Saturday: 'SAT',
  Sunday: 'SUN',
}

interface CalendarViewProps {
  calendar: CalendarDay[]
}

export default function CalendarView({ calendar }: CalendarViewProps) {
  if (!calendar || calendar.length === 0) {
    return (
      <div className="bg-gray-50 rounded-xl p-8 text-center text-sm text-gray-400">
        Calendar not yet generated. Run a scout to populate your week.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: `repeat(${calendar.length}, minmax(160px, 1fr))`, minWidth: '600px' }}
      >
        {calendar.map((day) => (
          <div key={day.day} className="flex flex-col">
            {/* Day header */}
            <div className="text-xs font-mono text-gray-400 mb-2 tracking-wider">
              {DAY_ABBREV[day.day] || day.day.slice(0, 3).toUpperCase()}
            </div>

            {/* Card */}
            <div className="bg-white border border-gray-100 rounded-xl p-4 flex-1">
              <p className="text-sm font-medium text-gray-900 leading-snug mb-2">
                {day.title}
              </p>
              {day.format && (
                <span className="inline-block bg-indigo-50 text-indigo-600 text-xs px-2 py-0.5 rounded-full mb-2">
                  {day.format}
                </span>
              )}
              {day.hook && (
                <p className="text-xs text-gray-500 leading-relaxed mt-1 italic">
                  &ldquo;{day.hook}&rdquo;
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
