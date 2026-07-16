"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Briefcase, ExternalLink, MapPin, DollarSign,
  Clock, BarChart3, CheckCircle2, Sparkles, Zap,
  Loader2, AlertCircle, AlertTriangle, XCircle,
  Activity, Target, MessageSquare, HelpCircle, ArrowRightLeft, FileText
} from "lucide-react";
import { ApplyAttempt, Job, KeywordAnalysis, InterviewQuestion, Resume, TaskProgress } from "../types";
import { useSafeAuth } from "../hooks/useSafeAuth";
import { apiGet, apiPost } from "@/lib/api";
import { ResumeDiffModal } from "./ResumeDiffModal";
import { CoverLetterModal } from "./CoverLetterModal";
import { ProcessTracker } from "./ProcessTracker";

import { AICareerCoach } from "./AICareerCoach";
import { RejectionAnalysis } from "./RejectionAnalysis";
import Link from "next/link";
import { getErrorMessage } from "@/utils/errors";

interface TailorTaskResponse {
  status: string;
  task_id: string;
}

export function JobCard({ job, index, onTailorSuccess }: { job: Job; index: number; onTailorSuccess?: () => void }) {
  const { getToken } = useSafeAuth();
  const [updatedJob, setUpdatedJob] = useState<Job | null>(null);
  const currentJob = updatedJob ?? job;
  const [loadingTailor, setLoadingTailor] = useState(false);
  const [tailorStatus, setTailorStatus] = useState<string | null>(null);
  const [tailorProgress, setTailorProgress] = useState<number>(0);
  const [tailorTaskState, setTailorTaskState] = useState<string>("queued");

  // Keyword Heatmap state
  const [showHeatmap, setShowHeatmap]           = useState(false);
  const [keywords, setKeywords]                 = useState<KeywordAnalysis | null>(null);
  const [loadingKeywords, setLoadingKeywords]   = useState(false);

  // Interview Questions state
  const [showQuestions, setShowQuestions]       = useState(!!(currentJob.interview_questions && currentJob.interview_questions.length > 0));
  const [questions, setQuestions]               = useState<InterviewQuestion[]>(currentJob.interview_questions || []);
  const [loadingQuestions, setLoadingQuestions] = useState(false);

  // Detailed Insights Collapsibility
  const [showDetails, setShowDetails] = useState(false);

  const tailorIntervalRef = React.useRef<NodeJS.Timeout | null>(null);

  const trackTailorTask = useCallback((taskId: string) => {
    setLoadingTailor(true);
    setTailorStatus("Tailoring starting...");
    setTailorProgress(10);
    setTailorTaskState("running");

    if (tailorIntervalRef.current) clearInterval(tailorIntervalRef.current);

    const interval = setInterval(async () => {
      try {
        const taskRes = await apiGet<TaskProgress>(`/tasks/${taskId}`, getToken);
        if (taskRes.status === "running" && taskRes.message) {
          setTailorStatus(taskRes.message);
          setTailorProgress(taskRes.progress || 0);
          setTailorTaskState("running");
        } else if (taskRes.status === "success" || taskRes.status === "completed" || taskRes.status === "successful") {
          setTailorStatus("Resume & cover letter tailored successfully!");
          setTailorProgress(100);
          setTailorTaskState("success");
          clearInterval(interval);
          // Refresh job data from FastAPI instead of Supabase
          try {
            const updatedJob = await apiGet<Job>(`/jobs/${currentJob.id}`, getToken);
            if (updatedJob) {
              setUpdatedJob(updatedJob);
              if (updatedJob.interview_questions?.length) {
                setQuestions(updatedJob.interview_questions);
                setShowQuestions(true);
              }
            }
          } catch (e) {
            console.error("Failed to refresh job after tailoring:", e);
          }
          if (onTailorSuccess) onTailorSuccess();
        } else if (taskRes.status === "failed" || taskRes.status === "failure") {
          setTailorStatus(`Tailoring failed: ${taskRes.message || "Unknown error"}`);
          setTailorProgress(0);
          setTailorTaskState("failed");
          clearInterval(interval);
        }
      } catch (e) {
        console.error("Error polling tailoring task:", e);
      }
    }, 1500);

    tailorIntervalRef.current = interval;
  }, [currentJob.id, getToken, onTailorSuccess]);


  useEffect(() => {
    const savedTailorTaskId = localStorage.getItem(`tailor-task-${currentJob.id}`);
    if (savedTailorTaskId) {
      const verifyActive = async () => {
        try {
          const taskRes = await apiGet<TaskProgress>(`/tasks/${savedTailorTaskId}`, getToken);
          if (taskRes.status === "running" || taskRes.status === "queued" || taskRes.status === "pending") {
            trackTailorTask(savedTailorTaskId);
          } else {
            localStorage.removeItem(`tailor-task-${currentJob.id}`);
          }
        } catch {
          localStorage.removeItem(`tailor-task-${currentJob.id}`);
        }
      };
      verifyActive();
    }
  }, [currentJob.id, getToken, trackTailorTask]);

  useEffect(() => {
    return () => {
      if (tailorIntervalRef.current) clearInterval(tailorIntervalRef.current);
    };
  }, []);


  const [error, setError] = useState<string | null>(null);

  // Resume Diff state
  const [showDiffModal, setShowDiffModal] = useState(false);
  const [showCoverLetterModal, setShowCoverLetterModal] = useState(false);
  const [baseResumeText, setBaseResumeText] = useState<string | null>(null);
  const [loadingBaseResume, setLoadingBaseResume] = useState(false);

  const handleOpenDiff = async () => {
    if (baseResumeText) {
      setShowDiffModal(true);
      return;
    }
    setLoadingBaseResume(true);
    setError(null);
    try {
      const resumes = await apiGet<Resume[]>("/resumes", getToken);
      if (resumes && resumes.length > 0) {
        const fullResume = await apiGet<Resume>(`/resumes/${resumes[0].id}`, getToken);
        if (!fullResume.content) {
          throw new Error("The selected resume has no readable content.");
        }
        setBaseResumeText(fullResume.content);
        setShowDiffModal(true);
      } else {
        setError("No base resume found. Please upload one in settings.");
      }
    } catch (error: unknown) {
      setError(getErrorMessage(error, "Failed to load base resume."));
    } finally {
      setLoadingBaseResume(false);
    }
  };

  // Auto-Apply states
  const [applying, setApplying] = useState(false);
  const [applyStatus, setApplyStatus] = useState<string | null>(null);
  const handleAutoApply = async (dryRun: boolean = true) => {
    setApplying(true);
    setApplyStatus("Queuing application...");
    setError(null);
    try {
      const res = await apiPost<{ status: string; task_id: string; attempt_id: string }>(
        `/jobs/${currentJob.id}/apply?dry_run=${dryRun}`,
        {},
        getToken
      );
      setApplyStatus("Browsing page...");

      // Polling fallback (Supabase realtime removed — polling is the sole mechanism)
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        if (attempts >= 20) { // 60s timeout
          clearInterval(interval);
          setApplying(false);
          setApplyStatus(null);
          return;
        }

        try {
          const attemptsList = await apiGet<ApplyAttempt[]>(`/jobs/${currentJob.id}/apply-status`, getToken);
          const current = attemptsList.find(a => a.id === res.attempt_id);
          if (current) {
            if (current.status === "success") {
              setApplyStatus("✅ Applied successfully!");
              clearInterval(interval);
              setTimeout(() => {
                setApplying(false);
                setApplyStatus(null);
              }, 4000);
            } else if (current.status === "failed") {
              setApplyStatus(`❌ Failed: ${current.error_msg || "Unknown error"}`);
              clearInterval(interval);
              setTimeout(() => {
                setApplying(false);
                setApplyStatus(null);
              }, 5000);
            } else if (current.status === "manual_required") {
              setApplyStatus("⚠️ Manual Intervention Required");
              clearInterval(interval);
              setTimeout(() => {
                setApplying(false);
                setApplyStatus(null);
              }, 5000);
            }
          }
        } catch (e) {
          console.error("Error polling apply status:", e);
        }
      }, 3000);



    } catch (error: unknown) {
      console.error("Error starting auto-apply:", error);
      setApplyStatus("Failed");
      setError(getErrorMessage(error, "Failed to start auto-apply"));
      setTimeout(() => {
        setApplying(false);
        setApplyStatus(null);
      }, 3000);
    }
  };

  const getScoreStyle = (score: number) => {
    if (score >= 7) return { text: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-500/20" };
    if (score >= 4) return { text: "text-amber-500",  bg: "bg-amber-500/10",  border: "border-amber-500/20"  };
    return              { text: "text-rose-500",    bg: "bg-rose-500/10",    border: "border-rose-500/20"    };
  };
  const scoreStyle = getScoreStyle(currentJob.score);

  const handleTailor = async () => {
    setLoadingTailor(true);
    setTailorStatus("Queuing tailoring task...");
    setTailorProgress(5);
    setTailorTaskState("queued");
    setError(null);
    try {
      const res = await apiPost<TailorTaskResponse>(`/jobs/${currentJob.id}/tailor`, {}, getToken);
      if (res && res.task_id) {
        localStorage.setItem(`tailor-task-${currentJob.id}`, res.task_id);
        trackTailorTask(res.task_id);
      } else {
        throw new Error("Invalid response from server");
      }
    } catch (error: unknown) {
      setTailorStatus(`❌ Failed to start tailoring: ${getErrorMessage(error, "Unknown error")}`);
      setTailorTaskState("failed");
      setTimeout(() => {
        setLoadingTailor(false);
        setTailorStatus(null);
      }, 4000);
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
      const data = await apiGet<KeywordAnalysis>(`/jobs/${currentJob.id}/keywords`, getToken);
      if (data.found.length === 0 && data.missing.length === 0) {
        setError("No keywords could be extracted from this job description.");
      } else {
        setKeywords(data);
        setShowHeatmap(true);
      }
    } catch (error: unknown) {
      setError(getErrorMessage(error, "Failed to analyze keywords."));
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
      const data = await apiGet<InterviewQuestion[]>(`/jobs/${currentJob.id}/interview-questions`, getToken);
      if (data.length === 0) {
        setError("No interview questions could be generated for this job.");
      } else {
        setQuestions(data);
        setShowQuestions(true);
      }
    } catch (error: unknown) {
      setError(getErrorMessage(error, "Failed to generate questions."));
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
      <div className="flex flex-col gap-4 mb-6">
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-3 flex-wrap">
            <Link href={`/jobs/${currentJob.id}`}>
              <h3 className="text-2xl font-bold text-[var(--foreground)] hover:text-indigo-500 hover:underline transition-colors cursor-pointer">
                {currentJob.title}
              </h3>
            </Link>
            <span 
              title="Holistic AI evaluation of your career trajectory and seniority. (Different from strict ATS Keyword Score)"
              className={`px-3 py-1 rounded-lg text-xs font-black uppercase tracking-widest border shadow-sm ${scoreStyle.bg} ${scoreStyle.text} ${scoreStyle.border}`}
            >
              {currentJob.score}/10 Fit
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm font-semibold text-[var(--muted-foreground)]">
            <span className="flex items-center gap-1.5 bg-[var(--background)] px-3 py-1.5 rounded-lg border border-[var(--border)]">
              <Briefcase className="w-4 h-4 text-indigo-400" /> {(currentJob.company && currentJob.company !== "nan") ? currentJob.company : "Unknown Company"}
            </span>
            <span className="flex items-center gap-1.5 bg-[var(--background)] px-3 py-1.5 rounded-lg border border-[var(--border)]">
              <MapPin className="w-4 h-4 text-rose-400" /> {currentJob.location || "Remote"}
            </span>
            {currentJob.salary && (
              <span className="flex items-center gap-1.5 bg-[var(--background)] px-3 py-1.5 rounded-lg border border-[var(--border)] text-emerald-400">
                <DollarSign className="w-4 h-4" /> {currentJob.salary}
              </span>
            )}
          </div>
          
          {/* Insights Toggle Button */}
          {(currentJob.found_skills?.length || currentJob.missing_skills?.length || currentJob.status === "rejected") && (
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="mt-4 flex items-center gap-2 text-xs font-bold text-indigo-500 hover:text-indigo-400 transition-colors"
            >
              <Target className="w-4 h-4" />
              {showDetails ? "Hide Insights & Analysis" : "View ATS Insights & Coach"}
            </button>
          )}

          <AnimatePresence>
            {showDetails && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                {/* ATS Overlap Heatmap & Gap Analysis */}
                {(currentJob.found_skills?.length || currentJob.missing_skills?.length) ? (
                  <div className="mt-4 flex flex-col gap-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Target className="w-4 h-4 text-indigo-400" />
                      <span className="text-xs font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                        ATS Overlap Heatmap
                      </span>
                      {currentJob.score !== undefined && (
                        <span className={`ml-auto text-xs font-bold px-2 py-0.5 rounded-md ${
                          currentJob.score >= 8 ? "bg-emerald-500/10 text-emerald-500" : 
                          currentJob.score >= 4 ? "bg-amber-500/10 text-amber-500" : 
                          "bg-rose-500/10 text-rose-500"
                        }`}>
                          {currentJob.score * 10}% ATS Match
                        </span>
                      )}
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Found Skills (Git Addition Style) */}
                      <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-4">
                        <h4 className="text-xs font-bold text-emerald-500 uppercase mb-3 flex items-center gap-2">
                          <CheckCircle2 className="w-4 h-4" /> Profile Overlap
                        </h4>
                        <div className="space-y-2">
                          {currentJob.found_skills?.map((skill) => (
                            <div key={skill} className="flex justify-between items-center text-sm font-medium">
                              <span className="text-emerald-400">+{skill}</span>
                              <span className="text-emerald-500/30 text-xs tracking-[0.1em]">████████</span>
                            </div>
                          ))}
                          {(!currentJob.found_skills || currentJob.found_skills.length === 0) && (
                            <span className="text-xs text-[var(--muted-foreground)]">No matching skills found.</span>
                          )}
                        </div>
                      </div>

                      {/* Missing Skills (Git Deletion Style) */}
                      <div className="bg-rose-500/5 border border-rose-500/20 rounded-xl p-4">
                        <h4 className="text-xs font-bold text-rose-500 uppercase mb-3 flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4" /> Gap Analysis
                        </h4>
                        <div className="space-y-2">
                          {currentJob.missing_skills?.map((skill) => (
                            <div key={skill} className="flex justify-between items-center text-sm font-medium">
                              <span className="text-rose-400">-{skill}</span>
                              <span className="text-rose-500/30 text-xs tracking-[0.1em]">████░░░░</span>
                            </div>
                          ))}
                          {(!currentJob.missing_skills || currentJob.missing_skills.length === 0) && (
                            <span className="text-xs text-[var(--muted-foreground)]">No missing skills detected!</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}

                {/* AI Career Coach */}
                {currentJob.status !== "rejected" && (
                  <div className="mt-4">
                    <AICareerCoach jobId={currentJob.id} missingSkills={currentJob.missing_skills} />
                  </div>
                )}

                {/* Rejection Analysis */}
                {currentJob.status === "rejected" && (
                  <div className="mt-4">
                    <RejectionAnalysis jobId={currentJob.id} />
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Action Bar */}
        <div className="flex flex-wrap items-center gap-3 w-full justify-start border-t border-[var(--border)] pt-4 mt-2">
          <a href={currentJob.url} target="_blank" rel="noopener noreferrer"
            className="bg-[var(--secondary)] hover:bg-[var(--border)] text-[var(--foreground)] p-3 rounded-xl transition-all"
            title="View Original Posting">
            <ExternalLink className="w-5 h-5" />
          </a>

          {currentJob.tailored_resume ? (
            <>
              <button onClick={handleOpenDiff} disabled={loadingBaseResume}
                className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/30 hover:border-emerald-500 text-emerald-500 px-4 py-3 rounded-xl text-sm font-bold transition-all">
                {loadingBaseResume ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRightLeft className="w-4 h-4" />}
                Diff Resume
              </button>
              {currentJob.cover_letter && (
                <button onClick={() => setShowCoverLetterModal(true)}
                  className="flex items-center gap-2 bg-pink-500/10 border border-pink-500/30 hover:border-pink-500 text-pink-500 px-4 py-3 rounded-xl text-sm font-bold transition-all">
                  <FileText className="w-4 h-4" />
                  Cover Letter
                </button>
              )}
            </>
          ) : (
            <button onClick={handleTailor} disabled={loadingTailor}
              className="flex items-center gap-2 bg-[var(--background)] border border-indigo-500/30 hover:border-indigo-500 text-indigo-500 px-4 py-3 rounded-xl text-sm font-bold transition-all disabled:opacity-50">
              {loadingTailor ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              Tailor
            </button>
          )}

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

          {/* Confidence-Gated Auto-Apply Button */}
          {applying ? (
            <button disabled
              className="flex items-center gap-2 bg-indigo-500/20 border border-indigo-500/30 text-indigo-400 px-5 py-3 rounded-xl text-sm font-bold animate-pulse">
              <Loader2 className="w-4 h-4 animate-spin animate-pulse" />
              {applyStatus}
            </button>
          ) : currentJob.score >= 8 ? (
            <button onClick={() => handleAutoApply(true)}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-3 rounded-xl text-sm font-bold transition-all shadow-md shadow-indigo-600/10"
              title="Autonomous application (Dry Run mode)">
              <Zap className="w-4 h-4 text-amber-400 animate-pulse" />
              Auto-Apply
            </button>
          ) : currentJob.score >= 4 ? (
            <button onClick={() => {
              if (confirm(`This is a potential match (score ${currentJob.score}/10). Auto-apply might be less accurate. Proceed with Dry Run?`)) {
                handleAutoApply(true);
              }
            }}
              className="flex items-center gap-2 bg-[var(--secondary)] border border-[var(--border)] hover:border-indigo-500 text-[var(--foreground)] px-5 py-3 rounded-xl text-sm font-bold transition-all"
              title="Requires manual confirmation due to lower score">
              <Zap className="w-4 h-4 text-[var(--muted-foreground)]" />
              Review & Apply
            </button>
          ) : (
            <button disabled
              className="flex items-center gap-2 bg-[var(--secondary)] text-[var(--muted-foreground)] px-5 py-3 rounded-xl text-sm font-bold border border-transparent opacity-40 cursor-not-allowed"
              title="Auto-apply disabled: Match score too low">
              <Zap className="w-4 h-4" />
              Unsuitable
            </button>
          )}

          <a href={currentJob.url} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-bold transition-all bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-400 hover:to-indigo-500 text-white shadow-lg shadow-indigo-500/25 hover:-translate-y-0.5">
            Apply Now
          </a>
        </div>
      </div>

      {/* Status banners */}
      <AnimatePresence>
        {error && (
          <motion.div key="error-alert" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
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

        {loadingTailor && tailorStatus && (
          <motion.div key="tailor-tracker" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="mb-4">
            <ProcessTracker
              type="tailor"
              status={tailorTaskState}
              message={tailorStatus}
              progress={tailorProgress}
              jobTitle={currentJob.title}
              company={currentJob.company}
              onDismiss={() => {
                setLoadingTailor(false);
                setTailorStatus(null);
                localStorage.removeItem(`tailor-task-${currentJob.id}`);
              }}
            />
          </motion.div>
        )}

        {applying && applyStatus && (
          <motion.div key="apply-tracker" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="mb-4">
            <ProcessTracker
              type="apply"
              status={
                applyStatus.includes("✅") ? "success" : 
                applyStatus.includes("❌") ? "failed" : 
                applyStatus.includes("⚠️") ? "manual_required" : 
                "running"
              }
              message={applyStatus}
              progress={
                applyStatus.includes("Queuing") ? 15 :
                applyStatus.includes("Browsing") ? 45 :
                applyStatus.includes("Filling") ? 75 :
                applyStatus.includes("✅") ? 100 :
                applyStatus.includes("❌") ? 0 : 90
              }
              jobTitle={currentJob.title}
              company={currentJob.company}
              onDismiss={() => {
                setApplying(false);
                setApplyStatus(null);
              }}
            />
          </motion.div>
        )}

        {showHeatmap && keywords && (
          <motion.div key="heatmap-panel" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
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
          <motion.div key="questions-panel" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
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
          { icon: <DollarSign className="w-3.5 h-3.5 text-emerald-500" />, label: "Salary", value: currentJob.salary || "Competitive" },
          { icon: <Clock       className="w-3.5 h-3.5 text-amber-500"  />, label: "Posted",  value: currentJob.date_posted || "Recently" },
          { icon: <BarChart3   className="w-3.5 h-3.5 text-pink-500"   />, label: "Source",  value: currentJob.site },
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
          &ldquo;{currentJob.reason}&rdquo;
        </p>
      </div>

      <ResumeDiffModal
        isOpen={showDiffModal}
        onClose={() => setShowDiffModal(false)}
        baseResume={baseResumeText || ""}
        tailoredResume={currentJob.tailored_resume || ""}
        jobTitle={currentJob.title}
        company={currentJob.company}
      />
      {currentJob.cover_letter && (
        <CoverLetterModal
          isOpen={showCoverLetterModal}
          onClose={() => setShowCoverLetterModal(false)}
          coverLetter={currentJob.cover_letter}
          jobTitle={currentJob.title}
          company={currentJob.company}
        />
      )}
    </motion.div>
  );
}
