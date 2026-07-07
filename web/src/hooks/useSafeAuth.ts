import { useAuth } from "@clerk/nextjs";

const pubKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
export const isClerkConfigured = !!(
  pubKey &&
  !pubKey.includes("REPLACE_ME") &&
  pubKey.startsWith("pk_")
);

const dummyGetToken = async () => "guest_token";
const dummySignOut = () => {};

function useDummyAuth() {
  return {
    isSignedIn: true,
    userId: "guest_user",
    getToken: dummyGetToken,
    signOut: dummySignOut,
  };
}

// Export the active hook based on Clerk configuration
export const useSafeAuth = isClerkConfigured ? useAuth : useDummyAuth;

