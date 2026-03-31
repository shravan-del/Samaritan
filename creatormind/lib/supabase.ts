import { createClient as createSupabaseClient } from '@supabase/supabase-js'
import { createServerClient as createSSRServerClient, type CookieOptions } from '@supabase/ssr'

// Client-side Supabase client (uses anon key)
// Uses || '' fallback so the module loads at build time without crashing;
// real values are always present at runtime via NEXT_PUBLIC_ env vars.
export const supabase = createSupabaseClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://placeholder.supabase.co',
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'placeholder'
)

// Server-side admin client (bypasses RLS — only for cron/webhook)
// Reads env vars at call time (runtime) not module load time (build time)
export function supabaseAdmin() {
  return createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    {
      auth: {
        autoRefreshToken: false,
        persistSession: false,
      },
    }
  )
}

// Route handler client that reads auth session from cookies
export async function createServerClient() {
  const { cookies } = await import('next/headers')
  const cookieStore = await cookies()
  return createSSRServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  {
    cookies: {
      get(name: string) {
        return cookieStore.get(name)?.value
      },
      set(name: string, value: string, options: CookieOptions) {
        try {
          cookieStore.set({ name, value, ...options })
        } catch {}
      },
      remove(name: string, options: CookieOptions) {
        try {
          cookieStore.set({ name, value: '', ...options })
        } catch {}
      },
    },
  })
}

// ─── Types ────────────────────────────────────────────────────────────────────

export type TopVideo = {
  videoId: string
  title: string
  viewCount: number
  likeCount: number
  description: string
  publishedAt: string
  thumbnailUrl: string
}

export type Creator = {
  id: string
  user_id: string
  channel_url: string | null
  channel_id: string | null
  channel_name: string | null
  channel_description: string | null
  subscriber_count: number | null
  total_videos: number | null
  top_videos: TopVideo[]
  niche: string | null
  content_pillars: string[]
  target_audience: string | null
  creator_voice: string | null
  strength_topics: string[]
  avoid_topics: string | null
  content_style: string | null
  unique_angle: string | null
  goals: string | null
  story: string | null
  inspirations: string | null
  posting_frequency: string | null
  biggest_challenge: string | null
  style_words: string | null
  stripe_customer_id: string | null
  stripe_subscription_id: string | null
  status: 'trial' | 'active' | 'cancelled'
  profile_built: boolean
  created_at: string
}

export type VideoIdea = {
  id: string
  creator_id: string
  title: string
  hook: string
  description: string | null
  thumbnail_concept: string | null
  format: string | null
  viral_score: number
  trend_source: string | null
  trend_url: string | null
  why_now: string | null
  estimated_views: string | null
  status: 'new' | 'saved' | 'dismissed' | 'used'
  week_of: string | null
  created_at: string
}

export type PivotOpportunity = {
  id: string
  creator_id: string
  niche: string
  rationale: string
  example_channels: string[]
  difficulty: 'easy' | 'medium' | 'hard'
  revenue_potential: string | null
  week_of: string | null
  created_at: string
}

export type CalendarDay = {
  day: string
  title: string
  hook: string
  format: string
  timing_reason?: string
}

export type WeeklyBrief = {
  id: string
  creator_id: string
  week_of: string
  summary: string
  top_trend: string | null
  calendar: CalendarDay[]
  format_to_steal: string | null
  platform_insight: string | null
  email_sent: boolean
  created_at: string
}
