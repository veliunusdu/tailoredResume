import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center relative">
      <div className="bg-blobs" />
      <div className="relative z-10 flex flex-col items-center gap-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="bg-gradient-to-br from-indigo-500 to-pink-500 p-2.5 rounded-xl shadow-lg shadow-indigo-500/30">
            <svg
              className="w-6 h-6 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"
              />
            </svg>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-gradient">
            TailoredResume
          </h1>
        </div>
        <p className="text-[var(--muted-foreground)] font-medium -mt-4">
          Your autonomous career intelligence command center.
        </p>
        <SignIn />
      </div>
    </div>
  );
}
