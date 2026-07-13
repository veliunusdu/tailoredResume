import { createClient } from "@/utils/supabase/server";
import { safeAuth } from "@/utils/safeAuth";
import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, XCircle } from "lucide-react";

// In Next.js 15+, page params are a Promise
export default async function JobDashboardPage(props: { params: Promise<{ id: string }> }) {
  const { userId } = await safeAuth();
  if (!userId) {
    redirect("/sign-in");
  }

  const { id } = await props.params;
  const supabase = await createClient();

  const { data: job, error } = await supabase
    .from("jobs")
    .select("*")
    .eq("id", id)
    .eq("user_id", userId)
    .single();

  if (error || !job) {
    return <div className="p-12 text-center text-red-500">Job not found.</div>;
  }

  // We can fetch the keywords analysis from the backend, but since it requires an LLM call,
  // we will fetch it client-side to show a loading state, OR we can fetch it here if we want to block render.
  // Wait, let's do a client-side component for the ATS score so it doesn't block page load!

  return (
    <div className="container max-w-5xl mx-auto py-12 px-4 space-y-8">
      <Link href="/jobs" className="text-sm font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 w-fit">
        <ArrowLeft className="w-4 h-4" /> Back to Jobs
      </Link>

      <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-8 shadow-sm">
        <h1 className="text-3xl font-black text-[var(--foreground)]">{job.title}</h1>
        <p className="text-lg text-[var(--muted-foreground)] mt-2">
          {job.company} &bull; {job.location} &bull; {job.salary || "Salary not specified"}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2 space-y-8">
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6">
            <h2 className="text-xl font-bold mb-4 text-[var(--foreground)]">Job Description</h2>
            <div className="prose prose-invert max-w-none text-sm text-[var(--muted-foreground)] whitespace-pre-wrap">
              {job.description}
            </div>
          </div>
          
          <CompanyDossier jobId={job.id} />
          
          <RoadmapPanel jobId={job.id} />
          
          <div className="pt-8 border-t border-[var(--border)]">
            <h2 className="text-xl font-bold mb-4 text-[var(--foreground)]">Interview Preparation</h2>
            <InterviewSimulator jobId={job.id} />
          </div>
        </div>

        <div className="space-y-8">
          <TailorPanel jobId={job.id} hasTailoredResume={!!job.tailored_resume} hasCoverLetter={!!job.cover_letter} />
          <AtsScorePanel jobId={job.id} />
          <SalaryInsightsPanel jobId={job.id} />
        </div>
      </div>
    </div>
  );
}

// Client component for fetching and rendering ATS score
import { AtsScorePanel } from "./AtsScorePanel";
import { RoadmapPanel } from "./RoadmapPanel";
import { InterviewSimulator } from "./InterviewSimulator";
import { CompanyDossier } from "./CompanyDossier";
import { TailorPanel } from "./TailorPanel";
import { SalaryInsightsPanel } from "./SalaryInsightsPanel";
