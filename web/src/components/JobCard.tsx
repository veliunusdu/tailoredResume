"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Briefcase, ExternalLink, MapPin, DollarSign,
  Clock, BarChart3, CheckCircle2, Sparkles, Zap,
  Loader2, AlertCircle, AlertTriangle, XCircle, RefreshCw,
  Activity, Target, MessageSquare, HelpCircle
} from "lucide-react";
import { Job, KeywordAnalysis, InterviewQuestion } from "../types";

export function JobCard({ job, index, sessionId }: { job: Job; index: number; sessionId?: string | null }) {
  const [loadingTailor, setLoadingTailor] = useState(false);
  const [tailorMsg, setTailorMsg]         = useState<string | null>(null);

  // Keyword Heatmap state
  const [showHeatmap, setShowHeatmap]           = useState(false);
  const [keywords, setKeywords]                 = useState<KeywordAnalysis | null>(null);
  const [loadingKeywords, setLoadingKeywords]   = useState(false);

  // Interview Questions state
  const [showQuestions, setShowQuestions]       = useState(false);
  const [questions, setQuestions]               = useState<InterviewQuestion[]>([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  const getScoreStyle = (score: number) => {
    if (score >= 7) return { text: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-500/20" };
    if (score >= 4) return { text: "text-amber-500",  bg: "bg-amber-500/10",  border: "border-amber-500/20"  };
    return              { text: "text-rose-500",    bg: "bg-rose-500/10",    border: "border-rose-500/20"    };
  };
  const scoreStyle = getScoreStyle(job.score);

  const handleTailor = async () => {
    setLoadingTailor(true);
    setTailorMsg(null);
    try {
      const headers: HeadersInit = sessionId ? { "X-Session-ID": sessionId } : {};
      const res = await fetch(`${apiUrl}/jobs/${job.id}/tailor`, { 
        method: "POST",
        headers
      });
      setTailorMsg(res.ok ? "✅ AI is tailoring your resume in the background…" : "❌ Failed to start tailoring.");
    } catch (_) {
      setTailorMsg("❌ Network error.");
    } finally {
      setLoadingTailor(false);
    }
  };

  const handleFetchKeywords = async () => {
    if (keywords) {
      setShowHeatmap(!showHeatmap);
      return;
    }
    setLoadingKeywords(true);
    setError(null);
    try {
      const headers: HeadersInit = sessionId ? { "X-Session-ID": sessionId } : {};
      const res = await fetch(`${apiUrl}/jobs/${job.id}/keywords`, { headers });
      if (res.ok) {
        const data = await res.json();
        if (data.found.length === 0 && data.missing.length === 0) {
          setError("No keywords could be extracted from this job description.");
        } else {
          setKeywords(data);
          setShowHeatmap(true);
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || "Failed to analyze keywords. Your API key might be invalid.");
      }
    } catch (_) {
      setError("Network error: Could not reach the API server.");
    } finally {
      setLoadingKeywords(false);
    }
  };

  const handleFetchQuestions = async () => {
    if (questions.length > 0) {
      setShowQuestions(!showQuestions);
      return;
    }
    setLoadingQuestions(true);
    setError(null);
    try {
      const headers: HeadersInit = sessionId ? { "X-Session-ID": sessionId } : {};
      const res = await fetch(`${apiUrl}/jobs/${job.id}/interview-questions`, { headers });
      if (res.ok) {
        const data = await res.json();
        if (data.length === 0) {
          setError("No interview questions could be generated for this job.");
        } else {
          setQuestions(data);
          setShowQuestions(true);
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || "Failed to generate questions. Check your API key.");
      }
    } catch (_) {
      setError("Network error: Could not reach the API server.");
    } finally {
      setLoadingQuestions(false);
    }
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.4 }}
      className="group glass rounded-2xl p-7 border border-[var(--border)] hover:shadow-xl hover:shadow-indigo-500/5 transition-all duration-300 relative overflow-hidden"
    >
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${scoreStyle.bg.replace("/10", "")} opacity-80`} />

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 mb-6">
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-3 flex-wrap">
            <h3 className="text-2xl font-bold text-[var(--foreground)] group-hover:text-indigo-500 transition-colors">
              {job.title}
            </h3>
            <span className={`px-3 py-1 rounded-lg text-xs font-black uppercase tracking-widest border shadow-sm ${scoreStyle.bg} ${scoreStyle.text} ${scoreStyle.border}`}>
              {job.score}/10 Fit
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm font-semibold text-[var(--muted-foreground)]">
            <span className="flex items-center gap-1.5 bg-[var(--background)] px-3 py-1.5 rounded-lg border border-[var(--border)]">
              <Briefcase className="w-4 h-4 text-indigo-400" /> {job.company}
            </span>
            <span className="flex items-center gap-1.5 bg-[var(--background)] px-3 py-1.5 rounded-lg border border-[var(--border)]">
              <MapPin className="w-4 h-4 text-rose-400" /> {job.location || "Remote"}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <a href={job.url} target="_blank" rel="noopener noreferrer"
            className="bg-[var(--secondary)] hover:bg-[var(--border)] text-[var(--foreground)] p-3 rounded-xl transition-all"
            title="View Original Posting">
            <ExternalLink className="w-5 h-5" />
          </a>

          <button onClick={handleTailor} disabled={loadingTailor}
            className="flex items-center gap-2 bg-[var(--background)] border border-indigo-500/30 hover:border-indigo-500 text-indigo-500 px-4 py-3 rounded-xl text-sm font-bold transition-all disabled:opacity-50">
            {loadingTailor ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            Tailor
          </button>

          <button onClick={handleFetchKeywords} disabled={loadingKeywords}
            className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-bold transition-all border ${showHeatmap ? "bg-indigo-500 text-white border-indigo-500" : "bg-[var(--background)] border-[var(--border)] text-[var(--foreground)] hover:border-indigo-500"}`}>
            {loadingKeywords ? <Loader2 className="w-4 h-4 animate-spin" /> : <Activity className="w-4 h-4" />}
            Heatmap
          </button>

          <button onClick={handleFetchQuestions} disabled={loadingQuestions}
            className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-bold transition-all border ${showQuestions ? "bg-amber-500 text-white border-amber-500" : "bg-[var(--background)] border-[var(--border)] text-[var(--foreground)] hover:border-amber-500"}`}>
            {loadingQuestions ? <Loader2 className="w-4 h-4 animate-spin" /> : <MessageSquare className="w-4 h-4" />}
            Questions
          </button>

          <a href={job.url} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-bold transition-all bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-400 hover:to-indigo-500 text-white shadow-lg shadow-indigo-500/25 hover:-translate-y-0.5">
            Apply Now
          </a>
        </div>
      </div>

      {/* Status banners */}
      <AnimatePresence>
        {error && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
            className="mb-4 p-3 rounded-xl flex items-center justify-between gap-2 text-sm font-medium bg-rose-500/10 text-rose-500 border border-rose-500/20">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="p-1 hover:bg-rose-500/20 rounded-md transition-colors">
              <XCircle className="w-4 h-4" />
            </button>
          </motion.div>
        )}

        {tailorMsg && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
            className={`mb-4 p-3 rounded-xl flex items-center gap-2 text-sm font-medium ${tailorMsg.startsWith("✅") ? "bg-emerald-500/10 text-emerald-500" : "bg-rose-500/10 text-rose-500"}`}>
            {tailorMsg}
          </motion.div>
        )}

        {showHeatmap && keywords && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
            className="mb-6 p-5 rounded-2xl bg-indigo-500/5 border border-indigo-500/20">
            <div className="flex items-center gap-2 mb-4">
              <Target className="w-4 h-4 text-indigo-500" />
              <h4 className="text-xs font-black uppercase tracking-widest text-indigo-500">ATS Keyword Heatmap</h4>
            </div>
            
            <div className="space-y-4">
              {keywords.missing.length > 0 && (
                <div>
                  <p className="text-[10px] font-black uppercase tracking-tighter text-rose-500/70 mb-2">Missing Keywords</p>
                  <div className="flex flex-wrap gap-2">
                    {keywords.missing.map(kw => (
                      <span key={kw} className="px-2.5 py-1 rounded-md bg-rose-500/10 border border-rose-500/20 text-rose-500 text-[10px] font-bold">
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {keywords.found.length > 0 && (
                <div>
                  <p className="text-[10px] font-black uppercase tracking-tighter text-emerald-500/70 mb-2">Found in Resume</p>
                  <div className="flex flex-wrap gap-2">
                    {keywords.found.map(kw => (
                      <span key={kw} className="px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 text-[10px] font-bold">
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {showQuestions && questions.length > 0 && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
            className="mb-6 p-5 rounded-2xl bg-amber-500/5 border border-amber-500/20">
            <div className="flex items-center gap-2 mb-4">
              <HelpCircle className="w-4 h-4 text-amber-500" />
              <h4 className="text-xs font-black uppercase tracking-widest text-amber-500">Tailored Interview Questions</h4>
            </div>
            
            <div className="space-y-4">
              {questions.map((q, i) => (
                <motion.div 
                  initial={{ opacity: 0, x: -10 }} 
                  animate={{ opacity: 1, x: 0 }} 
                  transition={{ delay: i * 0.1 }}
                  key={i} 
                  className="bg-[var(--background)] p-4 rounded-xl border border-[var(--border)]"
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <p className="text-sm font-bold text-[var(--foreground)]">
                      {q.question}
                    </p>
                    <span className="shrink-0 px-2 py-0.5 rounded text-[10px] font-black uppercase bg-[var(--secondary)] text-[var(--muted-foreground)]">
                      {q.type}
                    </span>
                  </div>
                  <p className="text-[11px] text-[var(--muted-foreground)] italic">
                    <b>Focus:</b> {q.focus}
                  </p>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Meta grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {[
          { icon: <DollarSign className="w-3.5 h-3.5 text-emerald-500" />, label: "Salary", value: job.salary || "Competitive" },
          { icon: <Clock       className="w-3.5 h-3.5 text-amber-500"  />, label: "Posted",  value: job.date_posted || "Recently" },
          { icon: <BarChart3   className="w-3.5 h-3.5 text-pink-500"   />, label: "Source",  value: job.site },
        ].map(({ icon, label, value }) => (
          <div key={label} className="bg-[var(--secondary)]/50 p-4 rounded-xl border border-[var(--border)]">
            <p className="text-[10px] font-black text-[var(--muted-foreground)] uppercase tracking-widest mb-1.5 flex items-center gap-1.5">
              {icon} {label}
            </p>
            <p className="text-sm font-bold text-[var(--foreground)]">{value}</p>
          </div>
        ))}
      </div>

      {/* AI Insight */}
      <div className={`rounded-xl p-5 border ${scoreStyle.border} ${scoreStyle.bg.replace("/10", "/5")}`}>
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
