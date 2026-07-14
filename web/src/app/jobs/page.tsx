"use client";

import { useEffect, useState } from "react";
import { JobCard } from "@/components/JobCard";
import { Job } from "@/types";
import { Search, MapPin, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { useSafeAuth } from "@/hooks/useSafeAuth";

export default function JobsPage() {
  const { getToken } = useSafeAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [qLocation, setQLocation] = useState("");
  const [qSkill, setQSkill] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiGet<Job[]>("/jobs", getToken);
        setJobs(data || []);
      } catch (e) {
        console.error("Failed to load jobs:", e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [getToken]);

  const filtered = jobs.filter((j) => {
    const locMatch = !qLocation || j.location?.toLowerCase().includes(qLocation.toLowerCase());
    const skillMatch = !qSkill || j.tags?.some((t) => t.toLowerCase().includes(qSkill.toLowerCase()));
    return locMatch && skillMatch;
  });

  return (
    <div className="container max-w-5xl mx-auto py-12 px-4 space-y-8">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <Link href="/" className="text-xs font-bold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 mb-2">
            <ArrowLeft className="w-3 h-3" /> Back to Dashboard
          </Link>
          <h1 className="text-3xl font-black tracking-tight text-[var(--foreground)]">Enriched Jobs</h1>
          <p className="text-[var(--muted-foreground)]">Browse and filter your AI-enriched job opportunities.</p>
        </div>
      </div>

      <div className="glass p-4 rounded-xl flex flex-col md:flex-row gap-4 border border-[var(--border)]">
        <div className="flex-1 relative">
          <MapPin className="absolute left-3 top-3 w-5 h-5 text-[var(--muted-foreground)]" />
          <input
            type="text"
            value={qLocation}
            onChange={(e) => setQLocation(e.target.value)}
            placeholder="Filter by location (e.g., Remote)"
            className="w-full pl-10 pr-4 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-3 w-5 h-5 text-[var(--muted-foreground)]" />
          <input
            type="text"
            value={qSkill}
            onChange={(e) => setQSkill(e.target.value)}
            placeholder="Filter by skill/tag (e.g., Python)"
            className="w-full pl-10 pr-4 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div className="space-y-6">
        {loading ? (
          <div className="text-center py-12 text-[var(--muted-foreground)]">Loading jobs...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 border border-[var(--border)] border-dashed rounded-xl glass">
            <p className="text-[var(--muted-foreground)] font-medium">No jobs found matching your filters.</p>
          </div>
        ) : (
          filtered.map((job, index) => (
            <JobCard key={job.id} job={job} index={index} />
          ))
        )}
      </div>
    </div>
  );
}
