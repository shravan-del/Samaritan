import { supabaseAdmin, createServerClient } from './supabase'

/**
 * Get the authenticated user from either:
 * 1. Authorization: Bearer <token> header (client-side fetch)
 * 2. Cookie-based session (SSR)
 */
export async function getAuthUser(req: Request) {
  const authHeader = req.headers.get('authorization')
  const token = authHeader?.replace('Bearer ', '')
  const admin = supabaseAdmin()

  // Try Bearer token first
  if (token) {
    const { data: { user } } = await admin.auth.getUser(token)
    if (user) return user
  }

  // Fallback to cookie-based session
  try {
    const supabase = await createServerClient()
    const { data: { user } } = await supabase.auth.getUser()
    if (user) return user
  } catch {
    // cookie reading may fail in some contexts
  }

  return null
}
