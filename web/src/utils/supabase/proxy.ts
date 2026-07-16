// Supabase has been removed from this project.
// The middleware previously used Supabase for auth session management.
// Auth is now handled by Clerk middleware in src/proxy.ts.
// This file is a stub only.

import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  // No-op: Supabase session management removed.
  return NextResponse.next({ request });
}
