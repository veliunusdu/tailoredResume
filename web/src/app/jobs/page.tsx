import { createClient } from "@/utils/supabase/server";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { JobCard } from "@/components/JobCard";
import { Job } from "@/types";
import { Search, MapPin } from "lucide-react";
import Link from "next/link";

export default async function JobsPage(props: {
  searchParams?: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { userId } = await auth();
  if (!userId) {
    redirect("/sign-in");
  }

  const supabase = await createClient();
  
  // Await searchParams in case of Next.js 15+ async params
  const params = await props.searchParams;
  const qLocation = (params?.location as string) || "";
  const qSkill = (params?.skill as string) || "";

  let query = supabase
    .from("jobs")
    .select("*")
    .eq("user_id", userId)
    .order("score", { ascending: false });

  if (qLocation) {
    query = query.ilike("location", `%${qLocation}%`);
  }
  if (qSkill) {
    // query.contains checks JSONB array elements
    query = query.contains("required_skills", `["${qSkill}"]`);
  }

  const { data: rawJobs, error } = await query;
  
  if (error) {
    console.error("Error fetching jobs from Supabase:", error);
  }

  // Cast and ensure tags are parsed correctly if needed
  const jobs = (rawJobs || []).map(row => ({
    ...row,
    tags: Array.isArray(row.tags) ? row.tags : JSON.parse(row.tags || "[]")
  })) as Job[];

  return (
    <div className="container max-w-5xl mx-auto py-12 px-4 space-y-8">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <Link href="/" className="text-xs font-bold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 mb-2">
            &larr; Back to Dashboard
          </Link>
          <h1 className="text-3xl font-black tracking-tight text-[var(--foreground)]">Enriched Jobs</h1>
          <p className="text-[var(--muted-foreground)]">Browse and filter your AI-enriched job opportunities.</p>
        </div>
      </div>

      <form className="glass p-4 rounded-xl flex flex-col md:flex-row gap-4 border border-[var(--border)]" action="/jobs" method="GET">
        <div className="flex-1 relative">
          <MapPin className="absolute left-3 top-3 w-5 h-5 text-[var(--muted-foreground)]" />
          <input 
            type="text" 
            name="location" 
            defaultValue={qLocation}
            placeholder="Filter by location (e.g., Remote)"
            className="w-full pl-10 pr-4 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-3 w-5 h-5 text-[var(--muted-foreground)]" />
          <input 
            type="text" 
            name="skill" 
            defaultValue={qSkill}
            placeholder="Filter by required skill (e.g., Python)"
            className="w-full pl-10 pr-4 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <button type="submit" className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2 rounded-lg font-bold transition-all">
          Apply Filters
        </button>
      </form>

      <div className="space-y-6">
        {jobs.length === 0 ? (
          <div className="text-center py-12 border border-[var(--border)] border-dashed rounded-xl glass">
            <p className="text-[var(--muted-foreground)] font-medium">No jobs found matching your filters.</p>
          </div>
        ) : (
          jobs.map((job, index) => (
            <JobCard key={job.id} job={job} index={index} />
          ))
        )}
      </div>
    </div>
  );
}
