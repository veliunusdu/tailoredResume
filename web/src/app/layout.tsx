import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TailoredResume — AI Career Intelligence",
  description:
    "Your autonomous career intelligence command center. AI-powered job discovery, resume tailoring, and application tracking.",
  keywords: ["resume", "job search", "AI", "career", "tailored resume"],
  openGraph: {
    title: "TailoredResume — AI Career Intelligence",
    description: "Autonomous job discovery and AI-powered resume tailoring.",
    type: "website",
  },
};

const pubKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
const isClerkConfigured = !!(
  pubKey &&
  !pubKey.includes("REPLACE_ME") &&
  pubKey.startsWith("pk_")
);

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const content = (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body suppressHydrationWarning className="min-h-full flex flex-col">{children}</body>
    </html>
  );

  if (isClerkConfigured) {
    return <ClerkProvider>{content}</ClerkProvider>;
  }

  return content;
}

