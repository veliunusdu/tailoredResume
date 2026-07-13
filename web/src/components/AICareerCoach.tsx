"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Loader2, Target, Clock, CheckCircle2, ChevronDown, ChevronUp } from "lucide-react";
import { apiGet } from "@/lib/api";
import { useSafeAuth } from "../hooks/useSafeAuth";

interface RoadmapStep {
  skill: string;
  action_items: string[];
  estimated_time: string;
}

interface SkillGapRoadmap {
  summary: string;
  steps: RoadmapStep[];
}

interface AICareerCoachProps {
  jobId: string;
  missingSkills: string[] | undefined;
}

export function AICareerCoach({ jobId, missingSkills }: AICareerCoachProps) {
  const { getToken } = useSafeAuth();
  const [expanded, setExpanded] = useState(false);
  const [roadmap, setRoadmap] = useState<SkillGapRoadmap | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasMissingSkills = missingSkills && missingSkills.length > 0;

  const handleToggle = async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    
    setExpanded(true);
    
    if (roadmap || loading) return;
    
    if (!hasMissingSkills) {
      setRoadmap({
        summary: "You have all the required skills for this job! You're good to go.",
        steps: []
      });
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await apiGet<SkillGapRoadmap>(`/jobs/${jobId}/roadmap`, getToken);
      setRoadmap(data);
    } catch (err: any) {
      setError(err.message || "Failed to generate roadmap.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-6 border border-purple-500/20 rounded-xl overflow-hidden bg-purple-500/5">
      <button 
        onClick={handleToggle}
        className="w-full p-4 flex items-center justify-between text-left hover:bg-purple-500/10 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <Sparkles className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h4 className="font-bold text-purple-400">AI Career Coach</h4>
            <p className="text-xs text-[var(--muted-foreground)]">
              {hasMissingSkills 
                ? "Generate a custom learning roadmap to bridge your skill gaps." 
                : "You match all requirements!"}
            </p>
          </div>
        </div>
        {expanded ? <ChevronUp className="w-5 h-5 text-purple-400" /> : <ChevronDown className="w-5 h-5 text-purple-400" />}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="p-4 pt-0 border-t border-purple-500/20">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-8 gap-3">
                  <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
                  <p className="text-sm text-[var(--muted-foreground)] animate-pulse">
                    Analyzing gaps and generating your custom roadmap...
                  </p>
                </div>
              ) : error ? (
                <div className="text-rose-400 text-sm py-4 text-center">
                  {error}
                </div>
              ) : roadmap ? (
                <div className="py-4 space-y-6">
                  <div className="bg-[var(--background)] border border-[var(--border)] rounded-xl p-4">
                    <p className="text-sm text-[var(--foreground)] leading-relaxed italic">
                      "{roadmap.summary}"
                    </p>
                  </div>

                  {roadmap.steps && roadmap.steps.length > 0 && (
                    <div className="space-y-4 relative">
                      {/* Timeline line */}
                      <div className="absolute left-[15px] top-4 bottom-4 w-px bg-purple-500/20" />
                      
                      {roadmap.steps.map((step, index) => (
                        <div key={index} className="relative pl-10">
                          {/* Node */}
                          <div className="absolute left-2 top-1.5 w-2 h-2 rounded-full bg-purple-400 shadow-[0_0_8px_rgba(168,85,247,0.5)]" />
                          
                          <div className="bg-[var(--background)] border border-[var(--border)] rounded-xl p-4">
                            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                              <h5 className="font-bold text-[var(--foreground)] flex items-center gap-2">
                                <Target className="w-4 h-4 text-purple-400" />
                                {step.skill}
                              </h5>
                              <span className="text-xs font-semibold px-2 py-1 bg-purple-500/10 text-purple-400 rounded-md flex items-center gap-1.5">
                                <Clock className="w-3 h-3" />
                                {step.estimated_time}
                              </span>
                            </div>
                            
                            <ul className="space-y-2">
                              {step.action_items.map((item, i) => (
                                <li key={i} className="text-sm text-[var(--muted-foreground)] flex items-start gap-2">
                                  <CheckCircle2 className="w-4 h-4 text-emerald-500/50 shrink-0 mt-0.5" />
                                  <span>{item}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
