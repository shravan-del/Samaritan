import Anthropic from '@anthropic-ai/sdk'
import type { Creator, VideoIdea, PivotOpportunity } from './supabase'
import type { TrendSignal } from './scout'

function stripMarkdownFences(text: string): string {
  return text
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/\s*```\s*$/, '')
    .trim()
}

function parseJSON<T>(text: string): T {
  const cleaned = stripMarkdownFences(text)
  try {
    return JSON.parse(cleaned) as T
  } catch {
    // Try to extract JSON from the response
    const jsonMatch = cleaned.match(/\{[\s\S]*\}|\[[\s\S]*\]/)
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]) as T
    }
    throw new Error(`Failed to parse AI response as JSON: ${cleaned.slice(0, 200)}`)
  }
}

export type CreatorProfileResult = {
  niche: string
  contentPillars: string[]
  creatorVoice: string
  audienceDescription: string
  strengthTopics: string[]
  avoidTopics: string
  contentStyle: string
  uniqueAngle: string
}

export async function buildCreatorProfile(params: {
  channelName: string
  channelDescription: string
  topVideos: { title: string; viewCount: number; description: string; publishedAt: string }[]
  story: string
  goals: string
  inspirations: string
  postingFrequency: string
  targetAudience: string
  avoidTopics: string
  styleWords: string
  biggestChallenge: string
}): Promise<CreatorProfileResult> {
  const client = new Anthropic()

  const topVideosText = params.topVideos
    .slice(0, 20)
    .map(
      (v, i) =>
        `${i + 1}. "${v.title}" — ${v.viewCount.toLocaleString()} views (${new Date(v.publishedAt).getFullYear()})`
    )
    .join('\n')

  const userPrompt = `Analyze this creator's data and build their content profile. Study their top videos carefully — the titles and view counts reveal what their audience actually responds to. Return ONLY valid JSON, no markdown.

CHANNEL NAME: ${params.channelName}
CHANNEL DESCRIPTION: ${params.channelDescription}

TOP VIDEOS (by views):
${topVideosText || 'No video data available'}

CREATOR'S STORY: ${params.story}
GOALS: ${params.goals}
INSPIRATIONS: ${params.inspirations}
POSTING FREQUENCY: ${params.postingFrequency}
TARGET AUDIENCE: ${params.targetAudience}
TOPICS TO AVOID: ${params.avoidTopics}
STYLE IN 3 WORDS: ${params.styleWords}
BIGGEST CHALLENGE: ${params.biggestChallenge}

Return this JSON schema exactly:
{
  "niche": "string — specific niche description",
  "contentPillars": ["pillar1", "pillar2", "pillar3", "pillar4"],
  "creatorVoice": "2-3 sentences describing how they write/speak and their personality",
  "audienceDescription": "specific description of their viewer",
  "strengthTopics": ["topic1", "topic2", "topic3", "topic4", "topic5"],
  "avoidTopics": "topics to avoid based on their stated preferences",
  "contentStyle": "e.g. educational storytelling with humor",
  "uniqueAngle": "what makes them different from others in their niche"
}`

  const msg = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 1024,
    system:
      "You are an expert YouTube strategist who has helped thousands of creators grow. You analyze creator data to build precise content DNA profiles that reveal exactly what makes each channel unique and what will help it grow.",
    messages: [{ role: 'user', content: userPrompt }],
  })

  const text = (msg.content[0] as { type: string; text: string }).text
  return parseJSON<CreatorProfileResult>(text)
}

export type GeneratedIdeasResult = {
  ideas: {
    title: string
    hook: string
    description: string
    thumbnailConcept: string
    format: string
    viralScore: number
    trendSource: string
    trendUrl: string
    whyNow: string
    estimatedViews: string
  }[]
  pivots: {
    niche: string
    rationale: string
    exampleChannels: string[]
    difficulty: 'easy' | 'medium' | 'hard'
    revenuePotential: string
  }[]
  formatToSteal: string
  platformInsight: string
}

export async function generateVideoIdeas(params: {
  creator: Creator
  trends: TrendSignal[]
  weekOf: string
}): Promise<GeneratedIdeasResult> {
  const client = new Anthropic()
  const { creator, trends } = params

  const trendsText = trends
    .map(
      (t, i) =>
        `${i + 1}. [${t.source.toUpperCase()}] "${t.title}" — ${t.engagement}\n   URL: ${t.url}\n   ${t.description.slice(0, 150)}`
    )
    .join('\n\n')

  const userPrompt = `CREATOR PROFILE:
Channel: ${creator.channel_name}
Niche: ${creator.niche}
Content Pillars: ${creator.content_pillars?.join(', ')}
Voice: ${creator.creator_voice}
Audience: ${creator.target_audience}
Unique Angle: ${creator.unique_angle}
Strength Topics: ${creator.strength_topics?.join(', ')}
Avoid: ${creator.avoid_topics}
Style: ${creator.content_style}
Subscriber Count: ${creator.subscriber_count?.toLocaleString() || 'Unknown'}

CURRENT TREND SIGNALS:
${trendsText}

Generate exactly 10 video ideas for this creator. Each idea MUST:
* Be written in their voice (${creator.creator_voice})
* Fit their niche (${creator.niche}) and pillars
* Capitalize on one of the trends listed above (cite which one)
* Have a title that sounds like something THEY would title a video, not a generic AI title
* Include a thumbnail concept that's visually distinct

Also generate 3 pivot opportunities — adjacent niches they could expand into. Identify one format from TikTok or short-form content they should test on YouTube this week. Give one sentence of platform insight about what's changing on YouTube right now.

Return ONLY valid JSON:
{
  "ideas": [
    {
      "title": "string",
      "hook": "string — first sentence of the video, in their voice",
      "description": "string — 2 sentences on what the video covers",
      "thumbnailConcept": "string",
      "format": "string — e.g. listicle, story, tutorial, reaction, vlog",
      "viralScore": number between 1-100,
      "trendSource": "string — which trend signal inspired this",
      "trendUrl": "string",
      "whyNow": "string — one sentence on why this will perform NOW",
      "estimatedViews": "string — e.g. 50k-200k based on their channel size"
    }
  ],
  "pivots": [
    {
      "niche": "string",
      "rationale": "string",
      "exampleChannels": ["channel1", "channel2"],
      "difficulty": "easy|medium|hard",
      "revenuePotential": "string"
    }
  ],
  "formatToSteal": "string",
  "platformInsight": "string"
}`

  const msg = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 4096,
    system:
      "You are a viral content strategist who has studied every successful YouTube channel. You know exactly what makes videos blow up. Your job is to match current trends to a specific creator's unique voice and audience — producing ideas that feel completely on-brand, not generic.",
    messages: [{ role: 'user', content: userPrompt }],
  })

  const text = (msg.content[0] as { type: string; text: string }).text
  const result = parseJSON<GeneratedIdeasResult>(text)

  // Sort ideas by viralScore descending
  result.ideas.sort((a, b) => b.viralScore - a.viralScore)

  return result
}

export type WeeklyBriefResult = {
  summary: string
  topTrend: string
  calendar: {
    day: string
    title: string
    hook: string
    format: string
    timing_reason: string
  }[]
}

export async function generateWeeklyBrief(params: {
  creator: Creator
  topIdeas: VideoIdea[]
  pivots: PivotOpportunity[]
  formatToSteal: string
  platformInsight: string
}): Promise<WeeklyBriefResult> {
  const client = new Anthropic()
  const { creator, topIdeas } = params

  const ideasText = topIdeas
    .slice(0, 5)
    .map((idea, i) => `${i + 1}. "${idea.title}"\n   Hook: ${idea.hook}\n   Viral Score: ${idea.viral_score}/100`)
    .join('\n\n')

  const firstName = creator.channel_name?.split(' ')[0] || creator.channel_name || 'there'

  const userPrompt = `Write a weekly brief for ${creator.channel_name}. Their niche: ${creator.niche}. Their voice: ${creator.creator_voice}.

Top 5 ideas this week:
${ideasText}

Write:
(1) A 3-sentence personal summary addressed to ${firstName} by name — mention something specific about their niche or the trends this week.
(2) One sentence about the biggest trend in their niche this week.
(3) A 5-day content calendar (Mon-Fri) assigning their best ideas to specific days with a reason for the timing.

Return ONLY valid JSON:
{
  "summary": "string — 3 sentences, warm and personal, addressed to ${firstName}",
  "topTrend": "string — one sentence about the biggest trend in their niche this week",
  "calendar": [
    {
      "day": "Monday",
      "title": "string",
      "hook": "string",
      "format": "string",
      "timing_reason": "string — why this day"
    },
    {
      "day": "Tuesday",
      "title": "string",
      "hook": "string",
      "format": "string",
      "timing_reason": "string"
    },
    {
      "day": "Wednesday",
      "title": "string",
      "hook": "string",
      "format": "string",
      "timing_reason": "string"
    },
    {
      "day": "Thursday",
      "title": "string",
      "hook": "string",
      "format": "string",
      "timing_reason": "string"
    },
    {
      "day": "Friday",
      "title": "string",
      "hook": "string",
      "format": "string",
      "timing_reason": "string"
    }
  ]
}`

  const msg = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 2048,
    system:
      "You are writing a personalized weekly content brief directly to a YouTube creator. Write like a smart, encouraging friend who knows their channel deeply — not like a corporate tool. Be specific, be warm, be actionable.",
    messages: [{ role: 'user', content: userPrompt }],
  })

  const text = (msg.content[0] as { type: string; text: string }).text
  return parseJSON<WeeklyBriefResult>(text)
}
