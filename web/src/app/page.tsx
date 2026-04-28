"use client";

import React, { useEffect, useState } from "react";
import { 
  Briefcase, 
  CheckCircle2, 
  HelpCircle, 
  ExternalLink, 
  Search, 
  Filter, 
  BarChart3, 
  LayoutDashboard,
  Target,
  Clock,
  DollarSign,
  MapPin,
  TrendingUp,
  Moon,
  Sun
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  date_posted: string;
  salary: string;
  description: string;
  site: string;
  score: number;
  verdict: string;
  reason: string;
}

interface Stats {
  total: number;
  strong: number;
  maybe: number;
  avg_score: number;
}

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [theme, setTheme] = useState("dark"); // Default to dark mode

  useEffect(() => {
    // Apply theme class to html element
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [jobsRes, statsRes] = await Promise.all([
          fetch("http://localhost:8000/jobs"),
          fetch("http://localhost:8000/stats")
        ]);
        const jobsData = await jobsRes.json();
        const statsData = await statsRes.json();
        setJobs(jobsData);
        setStats(statsData);
      } catch (error) {
        console.error("Error fetching data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const filteredJobs = jobs.filter(job => {
    const matchesSearch = job.title.toLowerCase().includes(search.toLowerCase()) || 
                          job.company.toLowerCase().includes(search.toLowerCase());
    const matchesFilter = filter === "all" || 
                          (filter === "strong" && job.score >= 7) ||
                          (filter === "maybe" && job.score >= 4 && job.score < 7);
    return matchesSearch && matchesFilter;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="bg-blobs" />
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-[var(--primary)] border-t-transparent rounded-full animate-spin"></div>
          <p className="text-[var(--muted-foreground)] animate-pulse font-medium">Initializing Dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen text-[var(--foreground)] p-6 lg:p-10 relative z-10">
      {/* Animated Background */}
      <div className="bg-blobs" />

      {/* Header */}
      <header className="max-w-7xl mx-auto mb-10 flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="bg-gradient-to-br from-indigo-500 to-pink-500 p-2.5 rounded-xl shadow-lg shadow-indigo-500/20">
              <Target className="text-white w-6 h-6" />
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-gradient">TailoredResume</h1>
          </div>
          <p className="text-[var(--muted-foreground)] font-medium">Your autonomous career intelligence command center.</p>
        </div>
        
        <div className="flex items-center gap-4">
          <button 
            onClick={toggleTheme}
            className="glass p-3 rounded-xl flex items-center justify-center text-[var(--foreground)] hover:scale-105 transition-transform"
            aria-label="Toggle Theme"
          >
            {theme === "dark" ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
          <div className="glass px-5 py-3 rounded-xl flex items-center gap-3 shadow-lg shadow-black/5">
            <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.8)]"></span>
            <span className="text-sm font-bold tracking-wide">API Operational</span>
          </div>
        </div>
      </header>

      {/* Stats Grid */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
        <StatCard 
          icon={<LayoutDashboard className="w-6 h-6 text-blue-500" />}
          label="Discovered Jobs"
          value={stats?.total || 0}
          subValue="Across all platforms"
          color="blue"
        />
        <StatCard 
          icon={<CheckCircle2 className="w-6 h-6 text-emerald-500" />}
          label="Strong Matches"
          value={stats?.strong || 0}
          subValue="Score ≥ 7/10"
          color="emerald"
        />
        <StatCard 
          icon={<HelpCircle className="w-6 h-6 text-amber-500" />}
          label="Potential Leads"
          value={stats?.maybe || 0}
          subValue="Score 4-6/10"
          color="amber"
        />
        <StatCard 
          icon={<TrendingUp className="w-6 h-6 text-indigo-500" />}
          label="Avg Fit Score"
          value={`${stats?.avg_score || 0}/10`}
          subValue="AI-powered analysis"
          color="indigo"
        />
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto">
        <div className="flex flex-col lg:flex-row gap-8">
          
          {/* Sidebar / Filters */}
          <aside className="w-full lg:w-80 space-y-6">
            <div className="glass p-6 rounded-2xl shadow-xl shadow-black/5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
              
              <h2 className="text-xl font-bold mb-6 flex items-center gap-2 relative z-10">
                <Filter className="w-5 h-5 text-indigo-500" />
                Refine Pipeline
              </h2>
              
              <div className="space-y-6 relative z-10">
                <div className="relative">
                  <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted-foreground)]" />
                  <input 
                    type="text" 
                    placeholder="Search roles or companies..."
                    className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl py-3 pl-10 pr-4 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all shadow-inner"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                
                <div className="space-y-3">
                  <label className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Quality Tier</label>
                  <div className="grid grid-cols-1 gap-2.5">
                    <FilterButton 
                      active={filter === "all"} 
                      onClick={() => setFilter("all")} 
                      label="All Discovered" 
                    />
                    <FilterButton 
                      active={filter === "strong"} 
                      onClick={() => setFilter("strong")} 
                      label="Strong Matches" 
                      count={stats?.strong}
                      color="emerald"
                    />
                    <FilterButton 
                      active={filter === "maybe"} 
                      onClick={() => setFilter("maybe")} 
                      label="Potential Leads" 
                      count={stats?.maybe}
                      color="amber"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="glass p-6 rounded-2xl border-l-4 border-l-pink-500 shadow-lg shadow-pink-500/10 bg-gradient-to-br from-pink-500/5 to-transparent relative overflow-hidden">
              <h3 className="font-bold text-lg mb-2 flex items-center gap-2">
                <LayoutDashboard className="w-5 h-5 text-pink-500" />
                Autonomous Mode
              </h3>
              <p className="text-sm text-[var(--muted-foreground)] font-medium mb-4 leading-relaxed">
                Run the background engine to refresh your pipeline with new opportunities.
              </p>
              <code className="block bg-[var(--background)] p-3 rounded-xl text-xs text-pink-500 font-mono mb-2 border border-pink-500/20 shadow-inner">
                python main.py run
              </code>
            </div>
          </aside>

          {/* Job Feed */}
          <div className="flex-1 space-y-4">
            <div className="flex items-center justify-between mb-4 glass px-6 py-4 rounded-2xl shadow-sm">
              <h2 className="text-2xl font-bold flex items-center gap-3">
                <Briefcase className="w-6 h-6 text-indigo-500" />
                Opportunity Feed
              </h2>
              <span className="bg-[var(--secondary)] text-[var(--foreground)] px-4 py-1.5 rounded-full text-sm font-bold shadow-inner">
                {filteredJobs.length} matches
              </span>
            </div>

            <AnimatePresence mode="popLayout">
              {filteredJobs.length > 0 ? (
                filteredJobs.map((job, index) => (
                  <JobCard key={job.id} job={job} index={index} />
                ))
              ) : (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="glass rounded-2xl p-20 text-center border-2 border-dashed border-[var(--border)] bg-gradient-to-b from-[var(--secondary)]/30 to-transparent"
                >
                  <div className="bg-[var(--background)] w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl shadow-black/5">
                    <Search className="w-10 h-10 text-[var(--muted-foreground)]" />
                  </div>
                  <h3 className="text-2xl font-bold mb-3">No matches found</h3>
                  <p className="text-[var(--muted-foreground)] font-medium text-lg">Try adjusting your filters or search terms.</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </main>
    </div>
  );
}

function StatCard({ icon, label, value, subValue, color }: { icon: React.ReactNode, label: string, value: string | number, subValue: string, color: string }) {
  const bgColors: Record<string, string> = {
    blue: "bg-blue-500/10",
    emerald: "bg-emerald-500/10",
    amber: "bg-amber-500/10",
    indigo: "bg-indigo-500/10",
  };
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass p-6 rounded-2xl group hover:-translate-y-1 transition-all duration-300 relative overflow-hidden shadow-lg shadow-black/5"
    >
      <div className={`absolute top-0 right-0 w-24 h-24 rounded-full blur-2xl -mr-10 -mt-10 opacity-50 transition-opacity group-hover:opacity-100 ${bgColors[color]}`}></div>
      
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-5 ${bgColors[color]} relative z-10`}>
        {icon}
      </div>
      <p className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-2 relative z-10">{label}</p>
      <h3 className="text-4xl font-extrabold text-[var(--foreground)] mb-2 tracking-tight relative z-10">{value}</h3>
      <p className="text-sm font-medium text-[var(--muted-foreground)] relative z-10">{subValue}</p>
    </motion.div>
  );
}

function FilterButton({ active, onClick, label, count, color = "indigo" }: { active: boolean, onClick: () => void, label: string, count?: number, color?: string }) {
  const colorStyles: Record<string, string> = {
    indigo: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border-indigo-500/30",
    emerald: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
    amber: "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30",
  };

  return (
    <button 
      onClick={onClick}
      className={`w-full text-left px-4 py-3 rounded-xl text-sm font-bold transition-all duration-300 flex items-center justify-between border ${
        active 
          ? `${colorStyles[color]} shadow-md` 
          : "border-transparent text-[var(--muted-foreground)] hover:bg-[var(--secondary)]"
      }`}
    >
      {label}
      {count !== undefined && (
        <span className={`text-[10px] px-2.5 py-1 rounded-full font-black ${active ? "bg-[var(--background)]" : "bg-[var(--background)]"}`}>
          {count}
        </span>
      )}
    </button>
  );
}

function JobCard({ job, index }: { job: Job, index: number }) {
  const getScoreStyle = (score: number) => {
    if (score >= 7) return { text: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-500/20" };
    if (score >= 4) return { text: "text-amber-500", bg: "bg-amber-500/10", border: "border-amber-500/20" };
    return { text: "text-rose-500", bg: "bg-rose-500/10", border: "border-rose-500/20" };
  };

  const scoreStyle = getScoreStyle(job.score);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.4 }}
      className="group glass rounded-2xl p-7 border border-[var(--border)] hover:shadow-xl hover:shadow-indigo-500/5 transition-all duration-300 relative overflow-hidden"
    >
      {/* Decorative gradient line */}
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${scoreStyle.bg.replace('/10', '')} opacity-80`}></div>

      <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 mb-6">
        <div className="space-y-2 flex-1">
          <div className="flex items-center gap-3 mb-2 flex-wrap">
            <h3 className="text-2xl font-bold text-[var(--foreground)] group-hover:text-indigo-500 transition-colors">{job.title}</h3>
            <span className={`px-3 py-1 rounded-lg text-xs font-black uppercase tracking-widest border ${scoreStyle.bg} ${scoreStyle.text} ${scoreStyle.border} shadow-sm`}>
              {job.score}/10 Fit
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-sm text-[var(--muted-foreground)] font-semibold">
            <span className="flex items-center gap-1.5 bg-[var(--background)] px-3 py-1.5 rounded-lg border border-[var(--border)] shadow-sm">
              <Briefcase className="w-4 h-4 text-indigo-400" /> {job.company}
            </span>
            <span className="flex items-center gap-1.5 bg-[var(--background)] px-3 py-1.5 rounded-lg border border-[var(--border)] shadow-sm">
              <MapPin className="w-4 h-4 text-rose-400" /> {job.location || "Remote"}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <a 
            href={job.url} 
            target="_blank" 
            rel="noopener noreferrer"
            className="bg-[var(--secondary)] hover:bg-[var(--border)] text-[var(--foreground)] p-3 rounded-xl transition-all shadow-sm group/btn"
            title="View Original Posting"
          >
            <ExternalLink className="w-5 h-5 group-hover/btn:scale-110 transition-transform" />
          </a>
          <button className="bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-400 hover:to-indigo-500 text-white px-6 py-3 rounded-xl text-sm font-bold shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 transition-all hover:-translate-y-0.5">
            Quick Apply
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-[var(--secondary)]/50 p-4 rounded-xl border border-[var(--border)]">
          <p className="text-[10px] font-black text-[var(--muted-foreground)] uppercase tracking-widest mb-1.5 flex items-center gap-1.5">
            <DollarSign className="w-3.5 h-3.5 text-emerald-500" /> Salary Range
          </p>
          <p className="text-sm font-bold text-[var(--foreground)]">{job.salary || "Competitive Market Rate"}</p>
        </div>
        <div className="bg-[var(--secondary)]/50 p-4 rounded-xl border border-[var(--border)]">
          <p className="text-[10px] font-black text-[var(--muted-foreground)] uppercase tracking-widest mb-1.5 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-amber-500" /> Discovered
          </p>
          <p className="text-sm font-bold text-[var(--foreground)]">{job.date_posted || "Recently"}</p>
        </div>
        <div className="bg-[var(--secondary)]/50 p-4 rounded-xl border border-[var(--border)]">
          <p className="text-[10px] font-black text-[var(--muted-foreground)] uppercase tracking-widest mb-1.5 flex items-center gap-1.5">
            <BarChart3 className="w-3.5 h-3.5 text-pink-500" /> Source
          </p>
          <p className="text-sm font-bold text-[var(--foreground)]">{job.site}</p>
        </div>
      </div>

      <div className={`rounded-xl p-5 border ${scoreStyle.border} ${scoreStyle.bg.replace('/10', '/5')}`}>
        <p className={`text-xs font-black uppercase tracking-[0.2em] mb-2.5 flex items-center gap-2 ${scoreStyle.text}`}>
          <CheckCircle2 className="w-4 h-4" /> AI Evaluation Insight
        </p>
        <p className="text-sm leading-relaxed text-[var(--foreground)]/80 font-medium">
          "{job.reason}"
        </p>
      </div>
    </motion.div>
  );
}
