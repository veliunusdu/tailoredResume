"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { Sparkles, ChevronRight, Loader2, CheckCircle2 } from "lucide-react";
import { ResumeUploader, UploadedResume } from "./ResumeUploader";
import { apiPost } from "@/lib/api";
import { useSafeAuth } from "@/hooks/useSafeAuth";

interface UnifiedLaunchpadProps {
  onSuccess: () => void;
}

export function UnifiedLaunchpad({ onSuccess }: UnifiedLaunchpadProps) {
  const [prompt, setPrompt] = useState("");
  const [uploadedResume, setUploadedResume] = useState<UploadedResume | null>(null);
  const [scouting, setScouting] = useState(false);
  const { getToken } = useSafeAuth();

  const handleLaunchScout = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadedResume && !prompt.trim()) return;

    setScouting(true);
    try {
      const token = await getToken();

      // 1. If there's a custom prompt/filter preference, save it to search config
      if (prompt.trim()) {
        await apiPost(
          "/search-config/chat",
          { text: prompt.trim() },
          () => Promise.resolve(token)
        );
      }

      // 2. Trigger sync of jobs
      await apiPost("/jobs/sync", {}, () => Promise.resolve(token));
      onSuccess();
    } catch (err) {
      console.error("Failed to launch scout:", err);
    } finally {
      setScouting(false);
    }
  };

  const isFormValid = uploadedResume || prompt.trim();

  return (
    <div className="max-w-3xl mx-auto space-y-10 py-8">
      <div className="text-center space-y-3">
        <h2 className="text-4xl font-black tracking-tight text-[var(--foreground)]">
          Set up your Autonomous Scout
        </h2>
        <p className="text-md text-[var(--muted-foreground)] font-medium max-w-lg mx-auto">
          Upload your resume and customize your job search filters in a single step to let the AI start scouting.
        </p>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass p-8 rounded-3xl border border-[var(--border)] relative overflow-hidden"
      >
        <div className="absolute top-0 right-0 p-8 opacity-5 pointer-events-none">
          <Sparkles className="w-48 h-48 text-indigo-500" />
        </div>

        <form onSubmit={handleLaunchScout} className="space-y-8 relative z-10">
          
          {/* Step 1: Resume Upload */}
          <div className="space-y-4">
            <label className="block text-sm font-bold text-[var(--foreground)] uppercase tracking-wider">
              Step 1: Upload Resume (Recommended)
            </label>
            <p className="text-xs text-[var(--muted-foreground)]">
              Drop your base resume. We&apos;ll automatically parse your skills, seniority, and experience to evaluate and score match compatibility.
            </p>
            
            <div className="relative">
              <ResumeUploader 
                onUploadSuccess={(resume) => {
                  setUploadedResume(resume);
                }} 
              />
              {uploadedResume && (
                <div className="absolute top-4 right-4 bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 px-3 py-1.5 rounded-lg flex items-center gap-1.5 text-xs font-bold shadow-sm">
                  <CheckCircle2 className="w-4 h-4" />
                  Uploaded: {uploadedResume.filename}
                </div>
              )}
            </div>
          </div>

          {/* Step 2: Custom Preferences */}
          <div className="space-y-4">
            <label className="block text-sm font-bold text-[var(--foreground)] uppercase tracking-wider">
              Step 2: Add Search Preferences (Optional)
            </label>
            <p className="text-xs text-[var(--muted-foreground)]">
              Tell the Search Agent where and what to search for in plain English.
            </p>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Find remote software engineer roles in the USA, paying at least $120k. No web3..."
              className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl p-4 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 resize-none h-28"
            />
          </div>

          {/* Action Button */}
          <div className="pt-4 border-t border-[var(--border)]">
            <button
              type="submit"
              disabled={scouting || !isFormValid}
              className="w-full py-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl font-bold transition-all flex justify-center items-center gap-2 disabled:opacity-40 shadow-lg shadow-indigo-500/15"
            >
              {scouting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" /> Launching Scout Engine...
                </>
              ) : (
                <>
                  Launch Autonomous Scout <ChevronRight className="w-5 h-5" />
                </>
              )}
            </button>
          </div>

        </form>
      </motion.div>
    </div>
  );
}
