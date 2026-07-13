"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { apiPost } from "@/lib/api";
import { Loader2, Sparkles, CheckCircle2 } from "lucide-react";

interface TailorTaskResponse {
  status: string;
  task_id: string;
}

export function TailorPanel({ jobId, hasTailoredResume }: { jobId: string, hasTailoredResume: boolean }) {
  const { getToken } = useAuth();
  const [toneStyle, setToneStyle] = useState("Professional");
  const [loading, setLoading] = useState(false);
  const [taskState, setTaskState] = useState<"idle" | "queued" | "running" | "success" | "failed">("idle");
  const [statusMsg, setStatusMsg] = useState("");

  const handleTailor = async () => {
    setLoading(true);
    setStatusMsg("Queuing tailoring task...");
    setTaskState("queued");
    try {
      const res = await apiPost<TailorTaskResponse>(`/jobs/${jobId}/tailor`, { tone_style: toneStyle }, getToken);
      if (res && res.task_id) {
        setStatusMsg("Tailoring in progress...");
        setTaskState("running");
        setTimeout(() => {
          setTaskState("success");
          setStatusMsg("Success! Refresh the page to view materials.");
          setLoading(false);
        }, 3000);
      }
    } catch (err: any) {
      setTaskState("failed");
      setStatusMsg(`Failed: ${err.message}`);
      setLoading(false);
    }
  };

  if (hasTailoredResume) {
    return (
      <div className="bg-[var(--card)] border border-emerald-500/20 rounded-2xl p-6 space-y-4">
        <h2 className="text-xl font-bold text-emerald-500 flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5" />
          Application Tailored
        </h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          Your resume and cover letter have been tailored for this position.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6 space-y-4">
      <h2 className="text-xl font-bold text-[var(--foreground)] flex items-center gap-2">
        <Sparkles className="w-5 h-5 text-indigo-400" />
        Tailor Application
      </h2>
      
      <div className="space-y-3">
        <label className="text-sm font-medium text-[var(--muted-foreground)] block">Cover Letter Tone</label>
        <select 
          value={toneStyle}
          onChange={(e) => setToneStyle(e.target.value)}
          disabled={loading}
          className="w-full bg-[var(--background)] border border-[var(--border)] rounded-lg p-2 text-sm text-[var(--foreground)] outline-none focus:border-indigo-500 transition-colors"
        >
          <option value="Professional">Professional (Standard)</option>
          <option value="Corporate">Corporate (Formal)</option>
          <option value="Startup">Startup (Enthusiastic & Direct)</option>
          <option value="Friendly">Friendly & Approachable</option>
          <option value="Bold">Bold & Confident</option>
        </select>
      </div>

      <button 
        onClick={handleTailor} 
        disabled={loading || taskState === "success"}
        className="w-full mt-4 flex justify-center items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 text-white px-4 py-2.5 rounded-lg text-sm font-bold transition-all"
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
        {loading ? "Tailoring..." : "Generate Materials"}
      </button>

      {statusMsg && (
        <p className={`text-xs mt-2 text-center ${taskState === "failed" ? "text-red-400" : taskState === "success" ? "text-emerald-400" : "text-indigo-400"}`}>
          {statusMsg}
        </p>
      )}
    </div>
  );
}
