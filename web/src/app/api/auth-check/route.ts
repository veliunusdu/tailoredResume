import { NextResponse } from "next/server";

export const runtime = "edge";

export async function GET() {
  const pubKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  const isClerkConfigured = !!(
    pubKey &&
    !pubKey.includes("REPLACE_ME") &&
    pubKey.startsWith("pk_")
  );

  return NextResponse.json({
    clerkConfigured: isClerkConfigured,
    environment: process.env.NODE_ENV,
    timestamp: Date.now(),
  });
}
