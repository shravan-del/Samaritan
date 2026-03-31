'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'

type Step = 1 | 2 | 3 | 4

interface FormData {
  channelUrl: string
  topVideoUrls: string
  story: string
  goals: string
  targetAudience: string
  inspirations: string
  postingFrequency: string
  biggestChallenge: string
  avoidTopics: string
  styleWords: string
}

const LOADING_MESSAGES = [
  'Fetching your top videos...',
  'Analyzing what works for your audience...',
  'Building your content profile...',
  'Setting up trend scouting...',
  'Your brain is ready!',
]

export default function OnboardPage() {
  const router = useRouter()
  const [step, setStep] = useState<Step>(1)
  const sessionRef = useRef<string | null>(null)

  // Keep sessionRef up-to-date with the latest auth token
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      sessionRef.current = data.session?.access_token ?? null
    })
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      sessionRef.current = session?.access_token ?? null
    })
    return () => subscription.unsubscribe()
  }, [])

  const [form, setForm] = useState<FormData>({
    channelUrl: '',
    topVideoUrls: '',
    story: '',
    goals: '',
    targetAudience: '',
    inspirations: '',
    postingFrequency: 'Weekly',
    biggestChallenge: 'Coming up with ideas',
    avoidTopics: '',
    styleWords: '',
  })
  const [channelPreview, setChannelPreview] = useState<{ name: string; subscribers: number } | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [loadingStep, setLoadingStep] = useState(0)
  const [error, setError] = useState('')

  function update(field: keyof FormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleStep1Next() {
    if (form.channelUrl) {
      setLoadingPreview(true)
      try {
        const res = await fetch(`/api/youtube-preview?url=${encodeURIComponent(form.channelUrl)}`)
        if (res.ok) {
          const data = await res.json()
          setChannelPreview(data)
        }
      } catch {
        // Non-fatal
      }
      setLoadingPreview(false)
    }
    setStep(2)
  }

  async function handleStep4() {
    setStep(4)
    setError('')

    // Animate loading messages
    for (let i = 0; i < LOADING_MESSAGES.length - 1; i++) {
      await new Promise((r) => setTimeout(r, i === 0 ? 500 : i === 2 ? 2000 : 1000))
      setLoadingStep(i + 1)
    }

    try {
      // Use token from auth state listener (most reliable)
      let token = sessionRef.current
      if (!token) {
        // Fallback: try getting session directly
        const { data: { session } } = await supabase.auth.getSession()
        token = session?.access_token ?? null
      }
      if (!token) {
        // Last resort: refresh to get a new token
        const { data: refreshData } = await supabase.auth.refreshSession()
        token = refreshData.session?.access_token ?? null
      }

      const res = await fetch('/api/onboard', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          channelUrl: form.channelUrl || undefined,
          topVideoUrls: form.topVideoUrls || undefined,
          story: form.story,
          goals: form.goals,
          inspirations: form.inspirations,
          postingFrequency: form.postingFrequency,
          targetAudience: form.targetAudience,
          avoidTopics: form.avoidTopics,
          styleWords: form.styleWords,
          biggestChallenge: form.biggestChallenge,
        }),
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.error || 'Onboarding failed')
      }

      setLoadingStep(4)
      await new Promise((r) => setTimeout(r, 800))
      router.push('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
      setStep(3)
    }
  }

  const progressPct = (step / 4) * 100

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top nav */}
      <div className="bg-white border-b border-gray-100">
        <div className="max-w-xl mx-auto px-6 h-16 flex items-center justify-between">
          <span className="text-lg font-bold text-indigo-600">CreatorMind</span>
          <span className="text-sm text-gray-400">Step {step === 4 ? 4 : step} of 4</span>
        </div>
        {/* Progress bar */}
        <div className="h-1 bg-gray-100">
          <div
            className="h-full bg-indigo-500 transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      <div className="max-w-xl mx-auto px-6 py-12">
        {/* Step 1 */}
        {step === 1 && (
          <div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Let&apos;s find your channel</h1>
            <p className="text-gray-500 mb-8">
              We&apos;ll use this to study what&apos;s working for you. We don&apos;t need login access.
            </p>

            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  YouTube channel URL
                </label>
                <input
                  type="url"
                  value={form.channelUrl}
                  onChange={(e) => update('channelUrl', e.target.value)}
                  className="input"
                  placeholder="https://youtube.com/@yourhandle"
                />
                {channelPreview && (
                  <div className="mt-2 flex items-center gap-2 text-sm text-green-700 bg-green-50 px-3 py-2 rounded-lg">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    {channelPreview.name} · {channelPreview.subscribers.toLocaleString()} subscribers
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Or paste your top 5 video URLs
                  <span className="text-gray-400 font-normal ml-1">(optional)</span>
                </label>
                <textarea
                  value={form.topVideoUrls}
                  onChange={(e) => update('topVideoUrls', e.target.value)}
                  className="input resize-none"
                  rows={4}
                  placeholder={'https://youtube.com/watch?v=...\nhttps://youtube.com/watch?v=...'}
                />
              </div>
            </div>

            <div className="mt-8 flex justify-end">
              <button
                onClick={handleStep1Next}
                disabled={loadingPreview}
                className="btn-primary px-8"
              >
                {loadingPreview ? 'Looking up channel...' : 'Next →'}
              </button>
            </div>
          </div>
        )}

        {/* Step 2 */}
        {step === 2 && (
          <div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Tell us about you</h1>
            <p className="text-gray-500 mb-8">
              The more specific you are, the better your content profile will be.
            </p>

            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  What&apos;s your channel about in one sentence? *
                </label>
                <input
                  type="text"
                  value={form.story}
                  onChange={(e) => update('story', e.target.value)}
                  className="input"
                  placeholder="I make videos about AI tools for software developers"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Who is your ideal viewer?
                </label>
                <input
                  type="text"
                  value={form.targetAudience}
                  onChange={(e) => update('targetAudience', e.target.value)}
                  className="input"
                  placeholder="e.g. developers who want to learn AI tools"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  What do you want to be known for in 2 years? *
                </label>
                <textarea
                  value={form.goals}
                  onChange={(e) => update('goals', e.target.value)}
                  className="input resize-none"
                  rows={3}
                  placeholder="I want to be the go-to channel for developers learning AI..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Who are your 2–3 biggest creator inspirations?
                </label>
                <input
                  type="text"
                  value={form.inspirations}
                  onChange={(e) => update('inspirations', e.target.value)}
                  className="input"
                  placeholder="e.g. MKBHD, Fireship, Ali Abdaal"
                />
              </div>
            </div>

            <div className="mt-8 flex items-center justify-between">
              <button onClick={() => setStep(1)} className="btn-ghost">
                ← Back
              </button>
              <button
                onClick={() => setStep(3)}
                disabled={!form.story || form.story.length < 10 || !form.goals || form.goals.length < 10}
                className="btn-primary px-8 disabled:opacity-50"
              >
                Next →
              </button>
            </div>
          </div>
        )}

        {/* Step 3 */}
        {step === 3 && (
          <div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">How you create</h1>
            <p className="text-gray-500 mb-8">
              This helps us understand your workflow and style.
            </p>

            {error && (
              <div className="bg-red-50 border border-red-100 text-red-700 text-sm rounded-lg px-4 py-3 mb-5">
                {error}
              </div>
            )}

            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  How often do you post?
                </label>
                <select
                  value={form.postingFrequency}
                  onChange={(e) => update('postingFrequency', e.target.value)}
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
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  What&apos;s your biggest challenge right now?
                </label>
                <select
                  value={form.biggestChallenge}
                  onChange={(e) => update('biggestChallenge', e.target.value)}
                  className="input"
                >
                  <option>Coming up with ideas</option>
                  <option>Writing titles and hooks</option>
                  <option>Staying consistent</option>
                  <option>Growing my audience</option>
                  <option>Monetizing my content</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Topics you NEVER want to cover
                  <span className="text-gray-400 font-normal ml-1">(optional)</span>
                </label>
                <input
                  type="text"
                  value={form.avoidTopics}
                  onChange={(e) => update('avoidTopics', e.target.value)}
                  className="input"
                  placeholder="e.g. politics, drama, controversy"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Describe your style in 3 words
                </label>
                <input
                  type="text"
                  value={form.styleWords}
                  onChange={(e) => update('styleWords', e.target.value)}
                  className="input"
                  placeholder="e.g. calm, educational, nerdy"
                />
              </div>
            </div>

            <div className="mt-8 flex items-center justify-between">
              <button onClick={() => setStep(2)} className="btn-ghost">
                ← Back
              </button>
              <button
                onClick={handleStep4}
                className="btn-primary px-8"
              >
                Build my brain →
              </button>
            </div>
          </div>
        )}

        {/* Step 4 — Loading */}
        {step === 4 && (
          <div className="text-center py-16">
            <div className="w-14 h-14 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-8" />

            <h1 className="text-2xl font-bold text-gray-900 mb-6">
              Building your CreatorMind...
            </h1>

            <div className="space-y-3 max-w-xs mx-auto">
              {LOADING_MESSAGES.slice(0, LOADING_MESSAGES.length - 1).map((msg, i) => (
                <div
                  key={msg}
                  className={`flex items-center gap-3 text-sm transition-all duration-300 ${
                    i <= loadingStep ? 'text-gray-900' : 'text-gray-300'
                  }`}
                >
                  <div
                    className={`w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center ${
                      i < loadingStep
                        ? 'bg-green-500'
                        : i === loadingStep
                        ? 'bg-indigo-500 animate-pulse'
                        : 'bg-gray-200'
                    }`}
                  >
                    {i < loadingStep && (
                      <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </div>
                  {msg}
                </div>
              ))}

              {loadingStep >= 4 && (
                <div className="text-green-600 font-semibold text-base mt-4">
                  Your brain is ready! ✓
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

