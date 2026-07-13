"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Briefcase,
  CheckCircle2,
  Search,
  Filter,
  Target,
  FileText,
  Loader2,
  RefreshCw,
  PlusCircle,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { UserButton } from "@clerk/nextjs";
import { useSafeAuth, isClerkConfigured } from "../hooks/useSafeAuth";
import { Job, Stats } from "../types";
import { JobCard } from "../components/JobCard";
import { ResumeUploader } from "../components/ResumeUploader";
import { SearchConfigPanel } from "../components/SearchConfigPanel";
import { apiGet, apiPost } from "@/lib/api";
import { createClient } from "../utils/supabase/client";
import { AnalyticsPanel } from "../components/AnalyticsPanel";
import { ProcessTracker } from "../components/ProcessTracker";
import { ProfileViewer } from "../components/ProfileViewer";
import { KanbanBoard } from "../components/KanbanBoard";

export default function Dashboard() {
  const { getToken } = useSafeAuth();

  // Data states
  const [resumes, setResumes] = useState<any[]>([]);
  const [searchConfig, setSearchConfig] = useState<any>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);

  // UI states
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<string | null>(null);
  const [syncProgress, setSyncProgress] = useState<number>(0);
  const [syncTaskStatus, setSyncTaskStatus] = useState<string>("queued");
  const [activeTab, setActiveTab] = useState<"feed" | "kanban" | "analytics" | "profile">("feed");

  const syncIntervalRef = React.useRef<NodeJS.Timeout | null>(null);
  const syncChannelRef = React.useRef<any | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [resumesData, configData, jobsData, statsData] = await Promise.all([
        apiGet<any[]>("/resumes", getToken),
        apiGet<any>("/search-config", getToken).catch(() => null), // might be 404 if not set
        apiGet<Job[]>("/jobs", getToken),
        apiGet<Stats>("/stats", getToken),
      ]);
      setResumes(resumesData || []);
      setSearchConfig(configData);
      setJobs(jobsData || []);
      setStats(statsData);
    } catch (error) {
      console.error("Error fetching data:", error);
    }
  }, [getToken]);

  const trackSyncTask = useCallback((taskId: string) => {
    setSyncing(true);
    setSyncStatus("Sync starting...");
    setSyncProgress(10);
    setSyncTaskStatus("running");

    if (syncIntervalRef.current) clearInterval(syncIntervalRef.current);
    if (syncChannelRef.current) syncChannelRef.current.unsubscribe();

    const supabase = createClient();
    const channel = supabase
      .channel(`sync-task-${taskId}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "task_progress",
          filter: `task_id=eq.${taskId}`,
        },
        async (payload: any) => {
          const data = payload.new;
          if (data.status === "running") {
            setSyncStatus(data.message);
            setSyncProgress(data.progress || 0);
            setSyncTaskStatus("running");
          } else if (data.status === "success") {
            setSyncStatus("Sync completed successfully!");
            setSyncProgress(100);
            setSyncTaskStatus("success");
            setTimeout(() => {
              setSyncing(false);
              setSyncStatus(null);
            }, 5000);
            channel.unsubscribe();
            await fetchData();
          } else if (data.status === "failed") {
            setSyncStatus(`Sync failed: ${data.message || "Unknown error"}`);
            setSyncProgress(0);
            setSyncTaskStatus("failed");
            setTimeout(() => {
              setSyncing(false);
              setSyncStatus(null);
            }, 6000);
            channel.unsubscribe();
          }
        }
      )
      .subscribe();

    const interval = setInterval(async () => {
      try {
        const taskRes = await apiGet<{ status: string; message: string; progress: number }>(`/tasks/${taskId}`, getToken);
        if (taskRes.status === "running" && taskRes.message) {
          setSyncStatus(taskRes.message);
          setSyncProgress(taskRes.progress || 0);
          setSyncTaskStatus("running");
        } else if (taskRes.status === "success" || taskRes.status === "completed" || taskRes.status === "successful") {
          setSyncStatus("Sync completed successfully!");
          setSyncProgress(100);
          setSyncTaskStatus("success");
          clearInterval(interval);
          channel.unsubscribe();
          setTimeout(() => {
            setSyncing(false);
            setSyncStatus(null);
          }, 5000);
          await fetchData();
        } else if (taskRes.status === "failed" || taskRes.status === "failure") {
          setSyncStatus(`Sync failed: ${taskRes.message || "Unknown error"}`);
          setSyncProgress(0);
          setSyncTaskStatus("failed");
          clearInterval(interval);
          channel.unsubscribe();
          setTimeout(() => {
            setSyncing(false);
            setSyncStatus(null);
          }, 6000);
        }
      } catch (e) {
        console.error("Error polling task:", e);
      }
    }, 1500);

    syncChannelRef.current = channel;
    syncIntervalRef.current = interval;
  }, [getToken, fetchData]);

  useEffect(() => {
    const initFetch = async () => {
      await fetchData();
      try {
        const activeTasks = await apiGet<any[]>("/tasks/active", getToken);
        const activeSync = Array.isArray(activeTasks) ? activeTasks.find(t => {
          const m = t.message?.toLowerCase() || "";
          return m.includes("sync") || m.includes("scouting") || m.includes("exclusion") || m.includes("listings") || m.includes("scoring compatibility");
        }) : null;
        if (activeSync) {
          trackSyncTask(activeSync.task_id);
        }
      } catch (e) {
        console.error("Error fetching active tasks:", e);
      }
      setLoading(false);
    };
    initFetch();
  }, [fetchData, getToken, trackSyncTask]);

  useEffect(() => {
    return () => {
      if (syncIntervalRef.current) clearInterval(syncIntervalRef.current);
      if (syncChannelRef.current) syncChannelRef.current.unsubscribe();
    };
  }, []);

  const handleSyncJobs = async () => {
    setSyncing(true);
    setSyncStatus("Sync queued...");
    setSyncProgress(5);
    setSyncTaskStatus("queued");
    try {
      const res = await apiPost<{ status: string; task_id: string }>("/jobs/sync", {}, getToken);
      trackSyncTask(res.task_id);
    } catch (error) {
      console.error("Error syncing jobs:", error);
      setSyncStatus("Failed");
      setSyncTaskStatus("failed");
      setTimeout(() => {
        setSyncing(false);
        setSyncStatus(null);
      }, 3000);
    }
  };

  const filteredJobs = jobs.filter((job) => {
    const matchesSearch =
      job.title.toLowerCase().includes(search.toLowerCase()) ||
      job.company.toLowerCase().includes(search.toLowerCase());
    const matchesFilter =
      filter === "all" ||
      (filter === "strong" && job.score >= 7) ||
      (filter === "maybe" && job.score >= 4 && job.score < 7);
    return matchesSearch && matchesFilter;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="bg-blobs" />
        <div className="flex flex-col items-center gap-4 relative z-10">
          <div className="w-12 h-12 border-4 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
          <p className="text-[var(--muted-foreground)] animate-pulse font-medium">
            Initializing AI Pipeline...
          </p>
        </div>
      </div>
    );
  }

  // Determine current onboarding step
  const hasResume = resumes.length > 0;
  const hasConfig = searchConfig && searchConfig.queries && searchConfig.queries.length > 0;

  return (
    <div className="min-h-screen text-[var(--foreground)] p-6 lg:p-10 relative z-10">
      <div className="bg-blobs" />

      {/* Header */}
      <header className="max-w-7xl mx-auto mb-10 flex flex-col md:flex-row md:items-end justify-between gap-6 relative z-10">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="bg-gradient-to-br from-indigo-500 to-pink-500 p-2.5 rounded-xl shadow-lg shadow-indigo-500/20">
              <Target className="text-white w-6 h-6" />
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-gradient">
              TailoredResume
            </h1>
          </div>
          <p className="text-[var(--muted-foreground)] font-medium">
            Your autonomous career intelligence command center.
          </p>
        </div>
        <div className="flex items-center gap-4">
          {isClerkConfigured && (
            <UserButton
              appearance={{
                elements: { avatarBox: "w-10 h-10 ring-2 ring-[var(--border)]" },
              }}
            />
          )}
        </div>
      </header>

      <main className="max-w-7xl mx-auto relative z-10">
        {!hasResume ? (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="max-w-2xl mx-auto mt-20">
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-indigo-500/10 text-indigo-400 mb-4 border border-indigo-500/20">
                <FileText className="w-8 h-8" />
              </div>
              <h2 className="text-3xl font-black mb-2 text-[var(--foreground)]">Step 1: Upload Your Base Resume</h2>
              <p className="text-[var(--muted-foreground)]">Our AI will extract your skills, experience, and profile to autonomously rank incoming jobs and tailor your applications.</p>
            </div>
            <ResumeUploader onUploadSuccess={fetchData} />
          </motion.div>
        ) : !hasConfig ? (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="max-w-3xl mx-auto mt-20">
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-pink-500/10 text-pink-400 mb-4 border border-pink-500/20">
                <Search className="w-8 h-8" />
              </div>
              <h2 className="text-3xl font-black mb-2 text-[var(--foreground)]">Step 2: Describe Your Ideal Job</h2>
              <p className="text-[var(--muted-foreground)]">Tell our AI what roles, locations, and salaries you want. We will automatically scout multiple job boards for you.</p>
            </div>
            <div className="bg-[var(--card)] p-6 rounded-2xl border border-[var(--border)] shadow-xl">
              <SearchConfigPanel onConfigSaved={fetchData} />
            </div>
          </motion.div>
        ) : (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-8">
            {/* Top Stats & Actions Bar */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 bg-[var(--card)] p-6 rounded-2xl border border-[var(--border)] shadow-sm">
              <div className="flex items-center gap-6">
                <div>
                  <p className="text-sm font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-1">AI Pipeline</p>
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-3 w-3">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                    </span>
                    <span className="font-bold text-[var(--foreground)]">Active & Monitoring</span>
                  </div>
                </div>
                <div className="h-10 w-px bg-[var(--border)] hidden md:block"></div>
                <div>
                  <p className="text-sm font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-1">Total Found</p>
                  <p className="font-bold text-[var(--foreground)]">{stats?.total || 0} Jobs</p>
                </div>
              </div>

              <div className="flex items-center gap-4 w-full md:w-auto">
                <button
                  onClick={handleSyncJobs}
                  disabled={syncing}
                  className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-indigo-500 hover:bg-indigo-600 text-white px-5 py-2.5 rounded-xl font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-500/20"
                >
                  <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
                  {syncing ? "Syncing..." : "Run Job Search"}
                </button>
              </div>
            </div>

            {syncing && syncStatus && (
              <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
                <ProcessTracker
                  type="sync"
                  status={syncTaskStatus}
                  message={syncStatus}
                  progress={syncProgress}
                  onDismiss={() => {
                    setSyncing(false);
                    setSyncStatus(null);
                  }}
                />
              </motion.div>
            )}

            {/* Main Tabs */}
            <div className="flex gap-4 border-b border-[var(--border)]">
              <button
                onClick={() => setActiveTab("feed")}
                className={`pb-3 text-sm font-bold transition-colors relative ${activeTab === "feed" ? "text-indigo-400" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"}`}
              >
                Intelligence Feed
                {activeTab === "feed" && <motion.div layoutId="activeTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500" />}
              </button>
              <button
                onClick={() => setActiveTab("analytics")}
                className={`pb-3 text-sm font-bold transition-colors relative ${activeTab === "analytics" ? "text-indigo-400" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"}`}
              >
                Analytics
                {activeTab === "analytics" && <motion.div layoutId="activeTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500" />}
              </button>
              <button
                onClick={() => setActiveTab("kanban")}
                className={`pb-3 text-sm font-bold transition-colors relative ${activeTab === "kanban" ? "text-indigo-400" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"}`}
              >
                Kanban
                {activeTab === "kanban" && <motion.div layoutId="activeTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500" />}
              </button>
              <button
                onClick={() => setActiveTab("profile")}
                className={`pb-3 text-sm font-bold transition-colors relative ${activeTab === "profile" ? "text-indigo-400" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"}`}
              >
                My Profile
                {activeTab === "profile" && <motion.div layoutId="activeTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500" />}
              </button>
            </div>

            {/* Tab Content */}
            {activeTab === "feed" ? (
              <div className="space-y-6">
                {/* Search & Filters */}
                <div className="flex flex-col md:flex-row gap-4">
                  <div className="relative flex-1 group">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--muted-foreground)] group-focus-within:text-indigo-400 transition-colors" />
                    <input
                      type="text"
                      placeholder="Search company, title, or keyword..."
                      className="w-full bg-[var(--card)] border border-[var(--border)] rounded-xl pl-12 pr-4 py-3 text-sm focus:outline-none focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/20 transition-all text-[var(--foreground)] placeholder:text-[var(--muted-foreground)]"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </div>
                  <div className="flex gap-2">
                    {[
                      { id: "all", label: "All Jobs" },
                      { id: "strong", label: "Strong Match (7+)" },
                      { id: "maybe", label: "Possible Fit (4-6)" },
                    ].map((f) => (
                      <button
                        key={f.id}
                        onClick={() => setFilter(f.id)}
                        className={`px-4 py-2 rounded-xl text-sm font-bold transition-all ${
                          filter === f.id
                            ? "bg-[var(--primary)] text-[var(--primary-foreground)] shadow-lg shadow-[var(--primary)]/20"
                            : "bg-[var(--card)] text-[var(--muted-foreground)] border border-[var(--border)] hover:border-[var(--primary)]/50 hover:text-[var(--foreground)]"
                        }`}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Job List */}
                <div className="space-y-4">
                  <AnimatePresence mode="popLayout">
                    {filteredJobs.length === 0 ? (
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="text-center py-20 border-2 border-dashed border-[var(--border)] rounded-2xl bg-[var(--card)]/50"
                      >
                        <Briefcase className="w-12 h-12 text-[var(--muted-foreground)] mx-auto mb-4 opacity-50" />
                        <h3 className="text-xl font-bold text-[var(--foreground)] mb-2">No jobs found</h3>
                        <p className="text-[var(--muted-foreground)]">Try running a sync or adjusting your filters.</p>
                      </motion.div>
                    ) : (
                      filteredJobs.map((job, idx) => (
                        <JobCard key={job.id} job={job} index={idx} onTailorSuccess={fetchData} />
                      ))
                    )}
                  </AnimatePresence>
                </div>
              </div>
            ) : activeTab === "kanban" ? (
              <KanbanBoard jobs={jobs} setJobs={setJobs} />
            ) : activeTab === "profile" ? (
              <ProfileViewer profile={resumes[0]?.structured_data} />
            ) : (
              <AnalyticsPanel stats={stats} jobs={jobs} />
            )}
          </motion.div>
        )}
      </main>
    </div>
  );
}
