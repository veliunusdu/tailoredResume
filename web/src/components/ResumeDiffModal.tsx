"use client";

import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, FileText, Check, AlertCircle, Copy, ArrowRightLeft } from "lucide-react";

interface ResumeDiffModalProps {
  isOpen: boolean;
  onClose: () => void;
  baseResume: string;
  tailoredResume: string;
  jobTitle: string;
  company: string;
}

export function ResumeDiffModal({
  isOpen,
  onClose,
  baseResume,
  tailoredResume,
  jobTitle,
  company
}: ResumeDiffModalProps) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  // Simple line-by-line diff
  const baseLines = baseResume.split("\n");
  const tailoredLines = tailoredResume.split("\n");
  const baseTrimmed = baseLines.map(l => l.trim());
  const tailoredTrimmed = tailoredLines.map(l => l.trim());

  const diffedBase = baseLines.map(line => {
    const trimmed = line.trim();
    const isRemoved = trimmed !== "" && !tailoredTrimmed.includes(trimmed);
    return { text: line, isRemoved };
  });

  const diffedTailored = tailoredLines.map(line => {
    const trimmed = line.trim();
    const isAdded = trimmed !== "" && !baseTrimmed.includes(trimmed);
    return { text: line, isAdded };
  });

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(tailoredResume);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy resume:", err);
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-6">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 bg-black/60 backdrop-blur-md"
        />

        {/* Modal Content */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ type: "spring", duration: 0.5 }}
          className="bg-[var(--card)] text-[var(--foreground)] w-full max-w-7xl h-[85vh] rounded-3xl border border-[var(--border)] shadow-2xl relative overflow-hidden flex flex-col z-10 glass"
        >
          {/* Header */}
          <header className="p-6 border-b border-[var(--border)] flex items-center justify-between gap-4 shrink-0 bg-[var(--secondary)]/20">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-xl border border-indigo-500/20">
                <ArrowRightLeft className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-xl font-bold flex items-center gap-2">
                  Resume Tailoring Diff
                </h2>
                <p className="text-xs text-[var(--muted-foreground)] font-semibold mt-0.5">
                  Comparing Base Resume against tailored version for <span className="text-indigo-400">{jobTitle} @ {company}</span>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleCopy}
                className="bg-[var(--secondary)] hover:bg-[var(--border)] border border-[var(--border)] text-[var(--foreground)] px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                {copied ? "Copied!" : "Copy Tailored Resume"}
              </button>
              <button
                onClick={onClose}
                className="p-2 hover:bg-[var(--secondary)] rounded-xl border border-transparent hover:border-[var(--border)] transition-all"
                aria-label="Close modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </header>

          {/* Info Banner */}
          <div className="px-6 py-3 bg-indigo-500/5 border-b border-[var(--border)] flex items-center gap-2 shrink-0">
            <AlertCircle className="w-4 h-4 text-indigo-400" />
            <p className="text-[11px] text-[var(--muted-foreground)] font-medium">
              Line-by-line diff. <span className="text-rose-400/90 font-bold bg-rose-500/10 px-1.5 py-0.5 rounded">Red highlights</span> show bullet points removed or reworded. <span className="text-emerald-400/90 font-bold bg-emerald-500/10 px-1.5 py-0.5 rounded">Green highlights</span> show tailored additions and JD keyword optimizations.
            </p>
          </div>

          {/* Dual Panel Diff */}
          <div className="flex-1 overflow-hidden grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-[var(--border)]">
            {/* Base Resume */}
            <div className="flex flex-col h-full overflow-hidden">
              <div className="px-6 py-3 bg-[var(--secondary)]/10 border-b border-[var(--border)] flex items-center gap-2 shrink-0">
                <FileText className="w-4 h-4 text-[var(--muted-foreground)]" />
                <span className="text-xs font-black uppercase tracking-wider text-[var(--muted-foreground)]">Base Resume</span>
              </div>
              <div className="flex-1 overflow-y-auto p-6 font-mono text-xs leading-relaxed space-y-0.5 bg-[var(--background)]/20">
                {diffedBase.map((line, idx) => (
                  <div
                    key={idx}
                    className={`px-2 py-0.5 rounded transition-colors whitespace-pre-wrap min-h-[1.2rem] ${
                      line.isRemoved ? "bg-rose-500/10 text-rose-400 border-l-2 border-rose-500" : "text-[var(--muted-foreground)]/80"
                    }`}
                  >
                    {line.text || " "}
                  </div>
                ))}
              </div>
            </div>

            {/* Tailored Resume */}
            <div className="flex flex-col h-full overflow-hidden">
              <div className="px-6 py-3 bg-[var(--secondary)]/10 border-b border-[var(--border)] flex items-center gap-2 shrink-0">
                <FileText className="w-4 h-4 text-indigo-400" />
                <span className="text-xs font-black uppercase tracking-wider text-indigo-400">Tailored Resume</span>
              </div>
              <div className="flex-1 overflow-y-auto p-6 font-mono text-xs leading-relaxed space-y-0.5 bg-[var(--background)]/20">
                {diffedTailored.map((line, idx) => (
                  <div
                    key={idx}
                    className={`px-2 py-0.5 rounded transition-colors whitespace-pre-wrap min-h-[1.2rem] ${
                      line.isAdded ? "bg-emerald-500/10 text-emerald-400 border-l-2 border-emerald-500 font-semibold" : "text-[var(--foreground)]"
                    }`}
                  >
                    {line.text || " "}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
