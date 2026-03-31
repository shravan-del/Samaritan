'use client'

import { useState } from 'react'
import Link from 'next/link'

const SAMPLE_IDEAS = [
  {
    title: 'I Tested Every AI Coding Tool So You Don\'t Have To',
    score: 94,
    format: 'listicle',
    source: 'YouTube trending',
    hook: 'I spent 40 hours testing 12 different AI coding tools — here\'s the brutal truth about which ones actually save time.',
  },
  {
    title: 'The Real Reason Junior Devs Can\'t Find Jobs in 2026',
    score: 88,
    format: 'opinion/story',
    source: 'Reddit r/cscareerquestions',
    hook: 'After reading 200+ comments from junior devs who can\'t get hired, I noticed the same pattern every single time.',
  },
  {
    title: 'Claude vs GPT-4o vs Gemini: I Built the Same App 3 Times',
    score: 82,
    format: 'comparison',
    source: 'web search',
    hook: 'Same prompt, same deadline, three completely different results — and the winner might surprise you.',
  },
]

const SAMPLE_CALENDAR = [
  { day: 'MON', title: 'AI Coding Tool Comparison', format: 'listicle' },
  { day: 'TUE', title: 'Why Junior Devs Struggle', format: 'story' },
  { day: 'WED', title: 'Claude vs GPT-4o vs Gemini', format: 'comparison' },
  { day: 'THU', title: 'The 5 VS Code Plugins I Actually Use', format: 'tutorial' },
  { day: 'FRI', title: 'Week Vlog: Shipping a Side Project', format: 'vlog' },
]

const FAQS = [
  {
    q: 'How does CreatorMind learn my style?',
    a: "We pull your top 20 videos from YouTube, analyze your titles, descriptions, and what gets the most views, then combine that with your answers to 8 questions. Claude AI builds a profile of your unique voice and niche.",
  },
  {
    q: 'Is this just a ChatGPT wrapper?',
    a: "No. Generic AI gives you generic ideas. CreatorMind actually fetches your real channel data, monitors Reddit and YouTube trending for your specific niche daily, and cross-references everything against your content profile. The ideas are personalized to you, not templated.",
  },
  {
    q: "What if I don't have many subscribers yet?",
    a: "CreatorMind works for channels of any size. The AI focuses on your content style and niche, not your subscriber count. Many of our users started with under 1,000 subscribers.",
  },
  {
    q: "How is this different from VidIQ or TubeBuddy?",
    a: "Those tools give you keyword data and analytics. We give you fully-formed video ideas written in your voice, a content calendar, and a weekly brief that synthesizes what's trending specifically for you. Different product, different job.",
  },
  {
    q: 'Can I cancel anytime?',
    a: "Yes. Cancel from your dashboard in one click. No emails, no phone calls, no retention tactics.",
  },
]

export default function LandingPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(null)

  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-white border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <span className="text-xl font-bold text-indigo-600 tracking-tight">CreatorMind</span>
          <div className="flex items-center gap-4">
            <Link href="/auth/login" className="text-sm text-gray-600 hover:text-gray-900 transition-colors">
              Sign in
            </Link>
            <Link href="/auth/signup" className="btn-primary">
              Start free trial
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="py-24 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-block bg-indigo-50 text-indigo-700 text-sm font-medium px-4 py-1.5 rounded-full mb-6">
            AI-powered content intelligence for YouTube creators
          </div>
          <h1 className="text-5xl font-bold text-gray-900 tracking-tight leading-tight">
            Your YouTube channel has a<br />
            <span className="text-indigo-600">second brain now.</span>
          </h1>
          <p className="text-xl text-gray-500 max-w-2xl mx-auto mt-5 leading-relaxed">
            CreatorMind learns your voice and style, scouts TikTok, Reddit, and YouTube daily,
            then tells you exactly what to make next — ranked by viral potential, written in your voice.
          </p>
          <div className="flex items-center justify-center gap-4 mt-8">
            <Link href="/auth/signup" className="btn-primary px-7 py-3 text-base">
              Start free trial — it&apos;s $0 for 7 days
            </Link>
            <a href="#how-it-works" className="btn-ghost text-base">
              See how it works
            </a>
          </div>
          <p className="text-sm text-gray-400 mt-4">
            No credit card required for trial · $19/mo after · Cancel anytime
          </p>
        </div>
      </section>

      {/* Social proof strip */}
      <div className="bg-gray-50 border-y border-gray-100 py-4">
        <div className="max-w-2xl mx-auto text-center text-sm text-gray-500">
          <span className="font-medium text-gray-700">50M+ creators</span> need this
          <span className="mx-3 text-gray-300">·</span>
          <span className="font-medium text-gray-700">7-day free trial</span>
          <span className="mx-3 text-gray-300">·</span>
          <span className="font-medium text-gray-700">Cancels in one click</span>
        </div>
      </div>

      {/* How it works */}
      <section id="how-it-works" className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-gray-900 text-center mb-3">
            Set it up in 5 minutes. Get ideas every week forever.
          </h2>
          <p className="text-gray-500 text-center mb-12">
            One-time setup. Weekly intelligence delivered to your inbox every Monday.
          </p>
          <div className="grid md:grid-cols-2 gap-8">
            {[
              {
                n: '01',
                title: 'Connect your channel',
                desc: "Paste your YouTube URL. We pull your top videos, analyze what's working, and study your style.",
              },
              {
                n: '02',
                title: 'Tell us your story',
                desc: "Answer 8 quick questions about your goals, audience, and what you want to be known for.",
              },
              {
                n: '03',
                title: 'We build your content brain',
                desc: "Claude AI studies your channel and builds a profile of your unique voice, niche, and content DNA.",
              },
              {
                n: '04',
                title: 'Get weekly intelligence',
                desc: "Every Monday you get 10 ranked video ideas, a 5-day calendar, and trend alerts — all written in your voice.",
              },
            ].map((step) => (
              <div key={step.n} className="flex gap-5">
                <div className="text-3xl font-black text-indigo-200 font-mono leading-none mt-1 flex-shrink-0 w-10">
                  {step.n}
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">{step.title}</h3>
                  <p className="text-gray-500 leading-relaxed">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Sample brief */}
      <section className="bg-gray-50 py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-gray-900 text-center mb-3">
            This is what you get every Monday.
          </h2>
          <p className="text-gray-500 text-center mb-10">
            Sample brief for <strong>Alex Chen</strong> — Tech Reviews (87k subscribers)
          </p>

          {/* Sample idea cards */}
          <div className="grid md:grid-cols-3 gap-4 mb-6">
            {SAMPLE_IDEAS.map((idea) => (
              <div key={idea.title} className="bg-white border border-gray-100 rounded-xl p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className={`text-xs font-mono font-medium px-2 py-0.5 rounded-full ${
                    idea.score >= 80 ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                  }`}>
                    {idea.score}/100
                  </span>
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                    {idea.format}
                  </span>
                </div>
                <h4 className="text-sm font-semibold text-gray-900 leading-snug mb-2">{idea.title}</h4>
                <p className="text-xs text-gray-500 italic leading-relaxed">&ldquo;{idea.hook}&rdquo;</p>
                <p className="text-xs text-indigo-500 mt-3">Source: {idea.source}</p>
              </div>
            ))}
          </div>

          {/* Calendar strip */}
          <div className="bg-white border border-gray-100 rounded-xl p-5">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-4">
              5-Day Content Calendar
            </p>
            <div className="grid grid-cols-5 gap-3">
              {SAMPLE_CALENDAR.map((day) => (
                <div key={day.day} className="text-center">
                  <div className="text-xs font-mono text-gray-400 mb-2">{day.day}</div>
                  <div className="bg-gray-50 rounded-lg p-2">
                    <p className="text-xs font-medium text-gray-800 leading-tight mb-1">{day.title}</p>
                    <span className="text-xs bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded">
                      {day.format}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-20 px-6">
        <div className="max-w-sm mx-auto text-center">
          <h2 className="text-3xl font-bold text-gray-900 mb-8">Simple pricing.</h2>
          <div className="ring-2 ring-indigo-500 rounded-2xl p-8 relative">
            <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
              <span className="bg-indigo-600 text-white text-xs font-semibold px-3 py-1 rounded-full">
                Most popular
              </span>
            </div>
            <div className="text-5xl font-black text-gray-900 mb-1">$19</div>
            <div className="text-gray-500 text-sm mb-1">/month</div>
            <div className="text-green-600 text-sm font-medium mb-6">7-day free trial</div>
            <ul className="text-sm text-gray-600 space-y-3 mb-8 text-left">
              {[
                'Weekly AI content brief',
                '10 ranked video ideas weekly',
                '5-day content calendar',
                'Pivot opportunity alerts',
                'Daily trend scouting',
                'Monday morning email delivery',
              ].map((f) => (
                <li key={f} className="flex items-center gap-2.5">
                  <svg className="w-4 h-4 text-green-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                  {f}
                </li>
              ))}
            </ul>
            <Link href="/auth/signup" className="btn-primary w-full block text-center">
              Start your free trial
            </Link>
            <p className="text-xs text-gray-400 mt-3">No credit card required · Cancel anytime</p>
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="bg-gray-50 py-16 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-10">
            Creators love it.
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                quote:
                  "I went from posting twice a month to every week because I always know what to make. My last video got 3x my usual views using one of CreatorMind's ideas.",
                name: 'Jordan K.',
                desc: 'Gaming channel, 34k subscribers',
              },
              {
                quote:
                  "The weekly brief feels like having a YouTube strategist on my team. It literally writes the hook for me. Worth every penny.",
                name: 'Priya M.',
                desc: 'Personal finance creator, 12k subscribers',
              },
              {
                quote:
                  "I was about to quit. CreatorMind suggested a pivot to 'tech for non-techies' and my last 4 videos all outperformed my channel average.",
                name: 'Marcus T.',
                desc: 'Tech reviewer, 67k subscribers',
              },
            ].map((t) => (
              <div key={t.name} className="bg-white border border-gray-100 rounded-xl p-6">
                <p className="text-sm text-gray-700 leading-relaxed mb-4">&ldquo;{t.quote}&rdquo;</p>
                <div>
                  <div className="text-sm font-semibold text-gray-900">{t.name}</div>
                  <div className="text-xs text-gray-400">{t.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-16 px-6">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-10">
            Common questions
          </h2>
          <div className="space-y-2">
            {FAQS.map((faq, i) => (
              <div key={i} className="border border-gray-100 rounded-xl overflow-hidden">
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full text-left px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
                >
                  <span className="text-sm font-medium text-gray-900">{faq.q}</span>
                  <svg
                    className={`w-4 h-4 text-gray-400 flex-shrink-0 transition-transform ${openFaq === i ? 'rotate-180' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {openFaq === i && (
                  <div className="px-5 pb-4 text-sm text-gray-600 leading-relaxed">{faq.a}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 py-8 px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-400">CreatorMind</span>
          <div className="flex items-center gap-5 text-sm text-gray-400">
            <a href="mailto:hello@creatormind.ai" className="hover:text-gray-600 transition-colors">
              hello@creatormind.ai
            </a>
            <Link href="/privacy" className="hover:text-gray-600 transition-colors">Privacy</Link>
            <Link href="/terms" className="hover:text-gray-600 transition-colors">Terms</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
