import { Resend } from 'resend'
import type { WeeklyBrief, VideoIdea } from './supabase'

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
}

function getScoreColor(score: number): string {
  if (score >= 80) return '#15803d'
  if (score >= 60) return '#b45309'
  return '#6b7280'
}

function getScoreBg(score: number): string {
  if (score >= 80) return '#dcfce7'
  if (score >= 60) return '#fef3c7'
  return '#f3f4f6'
}

export async function sendWeeklyBrief(params: {
  to: string
  creatorName: string
  channelName: string
  brief: WeeklyBrief
  topIdeas: VideoIdea[]
}): Promise<void> {
  const { to, creatorName, channelName, brief, topIdeas } = params
  const resend = new Resend(process.env.RESEND_API_KEY)

  const top3 = topIdeas.slice(0, 3)
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'https://creatormind.ai'

  const calendarRows = brief.calendar
    .map(
      (day) => `
      <tr>
        <td style="padding: 10px 0; border-bottom: 1px solid #f3f4f6; vertical-align: top; width: 90px;">
          <span style="font-weight: 600; color: #111827; font-size: 13px;">${day.day}</span>
        </td>
        <td style="padding: 10px 0 10px 16px; border-bottom: 1px solid #f3f4f6;">
          <div style="font-weight: 500; color: #111827; font-size: 14px; margin-bottom: 3px;">${day.title}</div>
          <div style="color: #6b7280; font-size: 12px;">${day.format}</div>
        </td>
      </tr>`
    )
    .join('')

  const ideaCards = top3
    .map(
      (idea) => `
      <div style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; margin-bottom: 16px;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
          <span style="background: ${getScoreBg(idea.viral_score)}; color: ${getScoreColor(idea.viral_score)}; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 999px; font-family: monospace;">${idea.viral_score}/100</span>
          ${idea.format ? `<span style="background: #f3f4f6; color: #6b7280; font-size: 11px; padding: 3px 8px; border-radius: 999px;">${idea.format}</span>` : ''}
        </div>
        <div style="font-weight: 600; color: #111827; font-size: 15px; margin-bottom: 8px; line-height: 1.4;">${idea.title}</div>
        <div style="color: #6b7280; font-size: 13px; font-style: italic; margin-bottom: 10px;">"${idea.hook}"</div>
        ${idea.why_now ? `<div style="font-size: 12px; color: #4f46e5; background: #eef2ff; padding: 8px 12px; border-radius: 6px;"><strong>Why now:</strong> ${idea.why_now}</div>` : ''}
      </div>`
    )
    .join('')

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your CreatorMind Brief — Week of ${formatDate(brief.week_of)}</title>
</head>
<body style="margin: 0; padding: 0; background: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background: #f9fafb; padding: 40px 20px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; width: 100%;">

          <!-- Header -->
          <tr>
            <td style="background: #4f46e5; border-radius: 16px 16px 0 0; padding: 32px; text-align: center;">
              <div style="font-size: 24px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">CreatorMind</div>
              <div style="font-size: 14px; color: #c7d2fe; margin-top: 4px;">Your Weekly Content Brief</div>
              <div style="font-size: 12px; color: #a5b4fc; margin-top: 8px;">Week of ${formatDate(brief.week_of)}</div>
            </td>
          </tr>

          <!-- Main content -->
          <tr>
            <td style="background: #ffffff; padding: 40px 40px 32px;">

              <!-- Greeting -->
              <div style="font-size: 15px; color: #374151; line-height: 1.7; margin-bottom: 32px; padding-bottom: 32px; border-bottom: 2px solid #f3f4f6;">
                Hi ${creatorName},<br><br>
                ${brief.summary}
              </div>

              <!-- Top Trend -->
              <div style="margin-bottom: 32px;">
                <div style="font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #9ca3af; margin-bottom: 12px;">THIS WEEK'S TOP TREND</div>
                <div style="background: #fefce8; border: 1px solid #fef08a; border-radius: 10px; padding: 16px 20px; font-size: 14px; color: #854d0e; line-height: 1.6;">
                  ${brief.top_trend || 'Stay tuned for this week\'s top trend.'}
                </div>
              </div>

              <!-- Top 3 Ideas -->
              <div style="margin-bottom: 32px;">
                <div style="font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #9ca3af; margin-bottom: 12px;">YOUR TOP 3 IDEAS THIS WEEK</div>
                ${ideaCards}
              </div>

              <!-- 5-Day Calendar -->
              <div style="margin-bottom: 32px;">
                <div style="font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #9ca3af; margin-bottom: 12px;">YOUR 5-DAY CONTENT CALENDAR</div>
                <div style="background: #f9fafb; border-radius: 12px; padding: 8px 20px;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    ${calendarRows}
                  </table>
                </div>
              </div>

              <!-- Format to Test -->
              ${brief.format_to_steal ? `
              <div style="margin-bottom: 32px;">
                <div style="font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #9ca3af; margin-bottom: 12px;">FORMAT TO TEST THIS WEEK</div>
                <div style="background: #eef2ff; border-radius: 10px; padding: 16px 20px; font-size: 14px; color: #3730a3; line-height: 1.6;">
                  ${brief.format_to_steal}
                </div>
              </div>` : ''}

              <!-- Platform Insight -->
              ${brief.platform_insight ? `
              <div style="margin-bottom: 32px;">
                <div style="font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #9ca3af; margin-bottom: 12px;">PLATFORM INSIGHT</div>
                <div style="font-size: 14px; color: #374151; line-height: 1.7; border-left: 3px solid #4f46e5; padding-left: 16px;">
                  ${brief.platform_insight}
                </div>
              </div>` : ''}

              <!-- CTA -->
              <div style="text-align: center; padding: 24px; background: #f9fafb; border-radius: 12px;">
                <div style="font-size: 14px; color: #6b7280; margin-bottom: 16px;">See all 10 ranked ideas in your dashboard</div>
                <a href="${appUrl}/dashboard/ideas" style="display: inline-block; background: #4f46e5; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 8px; font-weight: 600; font-size: 14px;">View all 10 ideas →</a>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background: #f9fafb; border-radius: 0 0 16px 16px; padding: 24px 40px; border-top: 1px solid #e5e7eb; text-align: center;">
              <div style="font-size: 12px; color: #9ca3af;">
                <a href="${appUrl}/dashboard" style="color: #6b7280; text-decoration: none;">Dashboard</a>
                &nbsp;·&nbsp;
                <a href="${appUrl}/unsubscribe" style="color: #6b7280; text-decoration: none;">Unsubscribe</a>
                &nbsp;·&nbsp;
                <a href="${appUrl}" style="color: #6b7280; text-decoration: none;">creatormind.ai</a>
              </div>
              <div style="font-size: 11px; color: #d1d5db; margin-top: 8px;">
                You're receiving this because you subscribed with ${to}
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>`

  await resend.emails.send({
    from: `${process.env.RESEND_FROM_NAME || 'CreatorMind'} <${process.env.RESEND_FROM_EMAIL || 'brief@creatormind.ai'}>`,
    to,
    subject: `Your CreatorMind Brief — Week of ${formatDate(brief.week_of)}`,
    html,
  })
}
