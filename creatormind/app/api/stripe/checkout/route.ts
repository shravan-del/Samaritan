import { NextResponse } from 'next/server'
import Stripe from 'stripe'
import { createServerClient, supabaseAdmin } from '@/lib/supabase'

export async function POST() {
  try {
    const supabase = await createServerClient()
    const { data: { user }, error: authError } = await supabase.auth.getUser()

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
      apiVersion: '2024-04-10',
    })

    const admin = supabaseAdmin()
    const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'https://creatormind.ai'

    // Get creator record
    const { data: creator } = await admin
      .from('creators')
      .select('id, stripe_customer_id')
      .eq('user_id', user.id)
      .single()

    let customerId = creator?.stripe_customer_id

    // Create Stripe customer if not exists
    if (!customerId) {
      const customer = await stripe.customers.create({
        email: user.email,
        metadata: { user_id: user.id },
      })
      customerId = customer.id

      if (creator?.id) {
        await admin
          .from('creators')
          .update({ stripe_customer_id: customerId })
          .eq('id', creator.id)
      }
    }

    // Create checkout session
    const session = await stripe.checkout.sessions.create({
      customer: customerId,
      mode: 'subscription',
      line_items: [
        {
          price: process.env.STRIPE_PRICE_MONTHLY!,
          quantity: 1,
        },
      ],
      subscription_data: {
        trial_period_days: 7,
      },
      success_url: `${appUrl}/dashboard?upgraded=true`,
      cancel_url: `${appUrl}/dashboard`,
      metadata: {
        user_id: user.id,
      },
    })

    return NextResponse.json({ checkoutUrl: session.url })
  } catch (err) {
    console.error('Checkout error:', err)
    const message = err instanceof Error ? err.message : 'Failed to create checkout session'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
