"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";
import { apiGet } from "@/lib/api";
import { useSafeAuth } from "@/hooks/useSafeAuth";
import { Job } from "@/types";

// Client component for fetching and rendering ATS score
import { AtsScorePanel } from "./AtsScorePanel";
import { RoadmapPanel } from "./RoadmapPanel";
import { InterviewSimulator } from "./InterviewSimulator";
import { CompanyDossier } from "./CompanyDossier";
import { TailorPanel } from "./TailorPanel";
import { SalaryInsightsPanel } from "./SalaryInsightsPanel";

export default function JobDashboardPage() {
  const { getToken } = useSafeAuth();
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const load = async () => {
      try {
        const data = await apiGet<Job>(`/jobs/${id}`, getToken);
        setJob(data);
      } catch (e: any) {
        setError(e.message || "Job not found.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id, getToken]);

  if (loading) {
    return (
      <div className="p-12 flex justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (error || !job) {
    return <div className="p-12 text-center text-red-500">{error || "Job not found."}</div>;
  }

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
