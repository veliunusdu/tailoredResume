"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { SearchX, Loader2, AlertTriangle, ArrowRight, ChevronDown, ChevronUp } from "lucide-react";
import { apiGet } from "@/lib/api";
import { useSafeAuth } from "../hooks/useSafeAuth";
import { getErrorMessage } from "@/utils/errors";

interface RejectionReason {
  category: string;
  explanation: string;
  action_to_take: string;
}

interface RejectionAnalysisData {
  harsh_truth: string;
  reasons: RejectionReason[];
  next_steps: string;
}

export function RejectionAnalysis({ jobId }: { jobId: string }) {
  const { getToken } = useSafeAuth();
  const [expanded, setExpanded] = useState(false);
  const [analysis, setAnalysis] = useState<RejectionAnalysisData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleToggle = async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    
    setExpanded(true);
    if (analysis || loading) return;

    setLoading(true);
    setError(null);
    try {
      const data = await apiGet<RejectionAnalysisData>(`/jobs/${jobId}/rejection-analysis`, getToken);
      setAnalysis(data);
    } catch (error: unknown) {
      setError(getErrorMessage(error, "Failed to analyze rejection."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-4 border border-rose-500/20 rounded-xl overflow-hidden bg-rose-500/5">
      <button 
        onClick={handleToggle}
        className="w-full p-4 flex items-center justify-between text-left hover:bg-rose-500/10 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-rose-500/20 rounded-lg">
            <SearchX className="w-5 h-5 text-rose-400" />
          </div>
          <div>
            <h4 className="font-bold text-rose-400">Why was I rejected?</h4>
            <p className="text-xs text-[var(--muted-foreground)]">
              Get brutal, honest feedback on your profile gaps.
            </p>
          </div>
        </div>
        {expanded ? <ChevronUp className="w-5 h-5 text-rose-400" /> : <ChevronDown className="w-5 h-5 text-rose-400" />}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="p-4 pt-0 border-t border-rose-500/20">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-8 gap-3">
                  <Loader2 className="w-6 h-6 animate-spin text-rose-400" />
                  <p className="text-sm text-[var(--muted-foreground)] animate-pulse">
                    Analyzing profile gaps...
                  </p>
                </div>
              ) : error ? (
                <div className="text-rose-400 text-sm py-4 text-center">
                  {error}
                </div>
              ) : analysis ? (
                <div className="py-4 space-y-6">
                  {/* Harsh Truth */}
                  <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl p-4">
                    <h5 className="text-xs font-bold uppercase tracking-wider text-rose-500 mb-2 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4" /> The Harsh Truth
                    </h5>
                    <p className="text-sm font-semibold text-rose-400">
                      &ldquo;{analysis.harsh_truth}&rdquo;
                    </p>
                  </div>

                  {/* Reasons */}
                  <div className="space-y-4">
                    {analysis.reasons.map((r, i) => (
                      <div key={i} className="bg-[var(--background)] border border-[var(--border)] rounded-xl p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                          <h6 className="font-bold text-[var(--foreground)]">{r.category}</h6>
                        </div>
                        <p className="text-sm text-[var(--muted-foreground)] mb-3 leading-relaxed">
                          {r.explanation}
                        </p>
                        <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-lg p-3">
                          <h6 className="text-xs font-bold uppercase text-emerald-500 mb-1 flex items-center gap-1.5">
                            <ArrowRight className="w-3 h-3" /> Action to Take
                          </h6>
                          <p className="text-sm text-emerald-400/90">{r.action_to_take}</p>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Next Steps */}
                  <div className="text-center pt-2">
                    <p className="text-sm text-[var(--muted-foreground)] italic">
                      {analysis.next_steps}
                    </p>
                  </div>
                </div>
              ) : null}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
