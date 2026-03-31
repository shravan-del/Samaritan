'use client'

import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'
import type { Creator } from '@/lib/supabase'

export default function ProfilePage() {
  const [creator, setCreator] = useState<Creator | null>(null)
  const [loading, setLoading] = useState(true)
  const [editOpen, setEditOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')

  const [editForm, setEditForm] = useState({
    story: '',
    goals: '',
    inspirations: '',
    posting_frequency: '',
    target_audience: '',
    avoid_topics: '',
    style_words: '',
  })

  useEffect(() => {
    async function load() {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return

      const { data } = await supabase
        .from('creators')
        .select('*')
        .eq('user_id', user.id)
        .single()

      if (data) {
        setCreator(data as Creator)
        setEditForm({
          story: data.story || '',
          goals: data.goals || '',
          inspirations: data.inspirations || '',
          posting_frequency: data.posting_frequency || '',
          target_audience: data.target_audience || '',
          avoid_topics: data.avoid_topics || '',
          style_words: data.style_words || '',
        })
      }
      setLoading(false)
    }
    load()
  }, [])

  async function handleSave() {
    setSaving(true)
    setSaveMsg('')

    try {
      const res = await fetch('/api/onboard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channelUrl: creator?.channel_url || undefined,
          story: editForm.story,
          goals: editForm.goals,
          inspirations: editForm.inspirations,
          postingFrequency: editForm.posting_frequency,
          targetAudience: editForm.target_audience,
          avoidTopics: editForm.avoid_topics,
          styleWords: editForm.style_words,
          biggestChallenge: creator?.biggest_challenge || 'Coming up with ideas',
        }),
      })

      if (res.ok) {
        setSaveMsg('Profile updated! Rebuilding your content DNA...')
        setEditOpen(false)

        const { data: updated } = await supabase
          .from('creators')
          .select('*')
          .eq('user_id', (await supabase.auth.getUser()).data.user!.id)
          .single()

        if (updated) setCreator(updated as Creator)
      } else {
        setSaveMsg('Failed to save. Please try again.')
      }
    } catch {
      setSaveMsg('Something went wrong.')
    } finally {
      setSaving(false)
      setTimeout(() => setSaveMsg(''), 5000)
    }
  }

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="card animate-pulse h-32" />
        ))}
      </div>
    )
  }

  if (!creator) return null

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My Profile</h1>
          <p className="text-sm text-gray-400 mt-0.5">Your content DNA built by AI</p>
        </div>
        {saveMsg && (
          <span className="text-sm text-green-700 bg-green-50 px-3 py-1.5 rounded-lg">
            {saveMsg}
          </span>
        )}
      </div>

      {/* Channel stats */}
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Channel Stats</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="stat-card">
            <div className="text-lg font-bold text-gray-900">{creator.channel_name || '—'}</div>
            <div className="text-xs text-gray-400">Channel name</div>
          </div>
          <div className="stat-card">
            <div className="text-lg font-bold text-gray-900">
              {creator.subscriber_count?.toLocaleString() || '—'}
            </div>
            <div className="text-xs text-gray-400">Subscribers</div>
          </div>
          <div className="stat-card">
            <div className="text-lg font-bold text-gray-900">{creator.total_videos || '—'}</div>
            <div className="text-xs text-gray-400">Total videos</div>
          </div>
          <div className="stat-card">
            <div className="text-xs font-medium text-gray-600">
              {new Date(creator.created_at).toLocaleDateString()}
            </div>
            <div className="text-xs text-gray-400">Account created</div>
          </div>
        </div>
      </div>

      {/* Content DNA */}
      <div className="card">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-sm font-semibold text-gray-700">Content DNA</h2>
          <button onClick={() => setEditOpen(true)} className="btn-secondary text-xs">
            Edit profile
          </button>
        </div>

        <div className="space-y-5">
          <div>
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Niche</div>
            <div className="text-sm text-gray-800">{creator.niche || 'Not yet built'}</div>
          </div>

          {creator.content_pillars?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                Content Pillars
              </div>
              <div className="flex flex-wrap gap-2">
                {creator.content_pillars.map((p) => (
                  <span key={p} className="bg-indigo-50 text-indigo-700 text-xs px-2.5 py-1 rounded-full">
                    {p}
                  </span>
                ))}
              </div>
            </div>
          )}

          {creator.creator_voice && (
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
                Creator Voice
              </div>
              <p className="text-sm text-gray-700 leading-relaxed bg-gray-50 rounded-lg p-3">
                {creator.creator_voice}
              </p>
            </div>
          )}

          {creator.target_audience && (
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
                Audience
              </div>
              <div className="text-sm text-gray-700">{creator.target_audience}</div>
            </div>
          )}

          {creator.strength_topics?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                Strength Topics
              </div>
              <div className="flex flex-wrap gap-2">
                {creator.strength_topics.map((t) => (
                  <span key={t} className="bg-green-50 text-green-700 text-xs px-2.5 py-1 rounded-full">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {creator.avoid_topics && (
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
                Topics to Avoid
              </div>
              <div className="text-sm text-gray-700">{creator.avoid_topics}</div>
            </div>
          )}

          {creator.unique_angle && (
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
                Unique Angle
              </div>
              <p className="text-sm text-gray-700 leading-relaxed border-l-4 border-indigo-300 pl-3">
                {creator.unique_angle}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Danger zone */}
      <div className="card border-red-100">
        <h2 className="text-sm font-semibold text-red-700 mb-2">Danger zone</h2>
        <p className="text-xs text-gray-500 mb-3">
          This will clear your current profile and rebuild it from scratch using your latest data.
        </p>
        <button
          onClick={() => setEditOpen(true)}
          className="text-xs border border-red-200 text-red-600 hover:bg-red-50 px-3 py-2 rounded-lg transition-colors"
        >
          Rebuild my profile from scratch
        </button>
      </div>

      {/* Edit modal */}
      {editOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setEditOpen(false)} />
          <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-base font-bold text-gray-900">Edit Profile</h3>
              <button onClick={() => setEditOpen(false)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Channel description</label>
                <textarea
                  value={editForm.story}
                  onChange={(e) => setEditForm({ ...editForm, story: e.target.value })}
                  className="input resize-none"
                  rows={2}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Goals</label>
                <textarea
                  value={editForm.goals}
                  onChange={(e) => setEditForm({ ...editForm, goals: e.target.value })}
                  className="input resize-none"
                  rows={2}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Inspirations</label>
                <input
                  type="text"
                  value={editForm.inspirations}
                  onChange={(e) => setEditForm({ ...editForm, inspirations: e.target.value })}
                  className="input"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Posting frequency</label>
                <select
                  value={editForm.posting_frequency}
                  onChange={(e) => setEditForm({ ...editForm, posting_frequency: e.target.value })}
                  className="input"
                >
                  <option>Daily</option>
                  <option>3-4x per week</option>
                  <option>Weekly</option>
                  <option>Bi-weekly</option>
                  <option>Monthly</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Target audience</label>
                <input
                  type="text"
                  value={editForm.target_audience}
                  onChange={(e) => setEditForm({ ...editForm, target_audience: e.target.value })}
                  className="input"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Topics to avoid</label>
                <input
                  type="text"
                  value={editForm.avoid_topics}
                  onChange={(e) => setEditForm({ ...editForm, avoid_topics: e.target.value })}
                  className="input"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Style in 3 words</label>
                <input
                  type="text"
                  value={editForm.style_words}
                  onChange={(e) => setEditForm({ ...editForm, style_words: e.target.value })}
                  className="input"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setEditOpen(false)} className="btn-secondary text-sm">
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="btn-primary text-sm disabled:opacity-50"
              >
                {saving ? 'Rebuilding...' : 'Save & rebuild profile'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
