import { NextResponse } from 'next/server'
import { getChannelByUrl } from '@/lib/youtube'

export async function GET(req: Request) {
  const url = new URL(req.url)
  const channelUrl = url.searchParams.get('url')

  if (!channelUrl) {
    return NextResponse.json({ error: 'URL required' }, { status: 400 })
  }

  try {
    const channel = await getChannelByUrl(channelUrl)
    return NextResponse.json({
      name: channel.channelName,
      subscribers: channel.subscriberCount,
      videoCount: channel.videoCount,
    })
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Channel not found'
    return NextResponse.json({ error: message }, { status: 400 })
  }
}
