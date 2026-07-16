"use client";

import React from "react";
import { motion } from "framer-motion";
import { 
  RefreshCw, Sparkles, Zap, CheckCircle2, AlertCircle, Loader2,
  Globe, SlidersHorizontal, Cpu, Database, FileText, HelpCircle, Laptop
} from "lucide-react";

interface ProcessTrackerProps {
  type: "sync" | "tailor" | "apply";
  status: "queued" | "running" | "success" | "failed" | "manual_required" | string;
  message: string | null;
  progress: number;
  jobTitle?: string;
  company?: string;
  onDismiss?: () => void;
}

export function ProcessTracker({
  type,
  status,
  message,
  progress,
  jobTitle,
  company,
  onDismiss
}: ProcessTrackerProps) {
  // Define steps and icons based on process type
  let title = "";
  let icon = <RefreshCw className="w-5 h-5 animate-spin" />;
  let steps: { label: string; icon: React.ReactNode; range: [number, number] }[] = [];

  if (type === "sync") {
    title = "Autonomous Job Search Sync";
    icon = <RefreshCw className="w-5 h-5 text-indigo-400" />;
    steps = [
      { label: "Scouting", icon: <Globe className="w-4 h-4" />, range: [0, 39] },
      { label: "Filtering", icon: <SlidersHorizontal className="w-4 h-4" />, range: [40, 59] },
      { label: "Analyzing", icon: <Cpu className="w-4 h-4" />, range: [60, 79] },
      { label: "AI Scoring", icon: <Sparkles className="w-4 h-4" />, range: [80, 94] },
      { label: "Saving", icon: <Database className="w-4 h-4" />, range: [95, 100] }
    ];
  } else if (type === "tailor") {
    title = `AI Resume Tailoring`;
    if (jobTitle && company) {
      title += ` for ${jobTitle} at ${company}`;
    }
    icon = <Sparkles className="w-5 h-5 text-pink-400 animate-pulse" />;
    steps = [
      { label: "Analyzing", icon: <Cpu className="w-4 h-4" />, range: [0, 39] },
      { label: "Base Selection", icon: <FileText className="w-4 h-4" />, range: [40, 64] },
      { label: "Tailoring Bullets", icon: <Sparkles className="w-4 h-4" />, range: [65, 84] },
      { label: "Cover Letter", icon: <FileText className="w-4 h-4" />, range: [85, 91] },
      { label: "Interview Prep", icon: <HelpCircle className="w-4 h-4" />, range: [92, 100] }
    ];
  } else if (type === "apply") {
    title = `Auto-Apply Pipeline`;
    if (jobTitle && company) {
      title += ` to ${jobTitle} at ${company}`;
    }
    icon = <Zap className="w-5 h-5 text-amber-400" />;
    // Since auto-apply status mapping is based on message/status strings, we map them into progress
    steps = [
      { label: "Queuing", icon: <Database className="w-4 h-4" />, range: [0, 25] },
      { label: "Browsing", icon: <Globe className="w-4 h-4" />, range: [26, 50] },
      { label: "Filling Form", icon: <Laptop className="w-4 h-4" />, range: [51, 80] },
      { label: "Submitting", icon: <CheckCircle2 className="w-4 h-4" />, range: [81, 100] }
    ];
  }

  // Determine current active step index
  const activeStepIdx = steps.findIndex(step => progress >= step.range[0] && progress <= step.range[1]);

  const isFailed = status === "failed" || (message && message.toLowerCase().startsWith("❌"));
  const isSuccess = status === "success" || progress === 100;
  const isManual = status === "manual_required";

  return (
    <div className="glass p-5 rounded-2xl border border-[var(--border)] shadow-lg bg-gradient-to-br from-indigo-500/[0.02] to-transparent relative overflow-hidden transition-all duration-300">
      {/* Background glow */}
      <div className={`absolute top-0 right-0 w-32 h-32 rounded-full blur-3xl opacity-5 pointer-events-none ${
        isFailed ? "bg-rose-500" : isSuccess ? "bg-emerald-500" : "bg-indigo-500"
      }`} />

      {/* Header info */}
      <div className="flex items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-xl bg-[var(--background)] border border-[var(--border)] shadow-sm ${
            !isSuccess && !isFailed ? "animate-spin-slow" : ""
          }`}>
            {isFailed ? (
              <AlertCircle className="w-5 h-5 text-rose-500 animate-bounce" />
            ) : isManual ? (
              <AlertCircle className="w-5 h-5 text-amber-500 animate-pulse" />
            ) : isSuccess ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-500" />
            ) : (
              icon
            )}
          </div>
          <div>
            <h4 className="font-bold text-sm text-[var(--foreground)]">{title}</h4>
            <p className="text-xs text-[var(--muted-foreground)] font-semibold mt-0.5 flex items-center gap-1.5">
              {!isSuccess && !isFailed && !isManual && <Loader2 className="w-3 h-3 animate-spin text-indigo-400" />}
              <span>{message || "Processing..."}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className={`text-xs font-black px-2.5 py-1 rounded-md border ${
            isFailed ? "bg-rose-500/10 text-rose-500 border-rose-500/20" :
            isManual ? "bg-amber-500/10 text-amber-500 border-amber-500/20" :
            isSuccess ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" :
            "bg-indigo-500/10 text-indigo-500 border-indigo-500/20"
          }`}>
            {isFailed ? "Failed" : isManual ? "Action Needed" : isSuccess ? "Done" : `${progress}%`}
          </span>
          {onDismiss && (isFailed || isSuccess || isManual) && (
            <button 
              onClick={onDismiss}
              className="text-xs font-bold text-[var(--muted-foreground)] hover:text-[var(--foreground)] bg-[var(--secondary)] hover:bg-[var(--border)] px-2.5 py-1 rounded-lg border border-[var(--border)] transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-[var(--secondary)] h-2 rounded-full overflow-hidden border border-[var(--border)] relative mb-5">
        <motion.div 
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className={`h-full rounded-full ${
            isFailed ? "bg-rose-500" :
            isManual ? "bg-amber-500" :
            isSuccess ? "bg-emerald-500" :
            "bg-gradient-to-r from-indigo-500 to-pink-500"
          }`}
        />
      </div>

      {/* Stepper Phases */}
      <div className="grid grid-cols-5 md:grid-cols-5 gap-2 pt-2 border-t border-[var(--border)]/40 relative">
        {steps.map((step, idx) => {
          const isCompleted = progress > step.range[1] || isSuccess;
          const isActive = idx === activeStepIdx && !isSuccess && !isFailed && !isManual;
          return (
            <div key={step.label} className="flex flex-col items-center text-center group">
              <div className={`w-7 h-7 rounded-lg border flex items-center justify-center transition-all duration-300 ${
                isFailed ? "bg-rose-500/5 border-rose-500/20 text-rose-400" :
                isCompleted 
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-500" 
                  : isActive 
                    ? "bg-indigo-500/10 border-indigo-500/50 text-indigo-400 ring-2 ring-indigo-500/20 scale-110" 
                    : "bg-[var(--background)] border-[var(--border)] text-[var(--muted-foreground)] opacity-50"
              }`}>
                {isCompleted ? <CheckCircle2 className="w-4 h-4" /> : step.icon}
              </div>
              <span className={`text-[10px] font-bold mt-1.5 transition-colors hidden sm:block ${
                isFailed ? "text-rose-400" :
                isCompleted ? "text-emerald-500/80" :
                isActive ? "text-indigo-400 font-extrabold" :
                "text-[var(--muted-foreground)] opacity-60"
              }`}>
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
