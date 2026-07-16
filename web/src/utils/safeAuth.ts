import { auth } from "@clerk/nextjs/server";

const pubKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
export const isClerkConfigured = !!(
  pubKey &&
  !pubKey.includes("REPLACE_ME") &&
  pubKey.startsWith("pk_")
);

export async function safeAuth() {
  if (isClerkConfigured) {
    try {
      return await auth();
    } catch {
      console.warn("Clerk auth failed (possibly invalid key). Falling back to guest.");
      return { userId: "guest_user", getToken: async () => "guest_token" };
    }
  }
  return { userId: "guest_user", getToken: async () => "guest_token" };
}
