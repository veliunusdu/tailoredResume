"use client";

import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, FileText, Check, Copy, ArrowRightLeft } from "lucide-react";

interface CoverLetterModalProps {
  isOpen: boolean;
  onClose: () => void;
  coverLetter: string;
  jobTitle: string;
  company: string;
}

export function CoverLetterModal({
  isOpen,
  onClose,
  coverLetter,
  jobTitle,
  company
}: CoverLetterModalProps) {
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

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(coverLetter);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy cover letter:", err);
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
          className="bg-[var(--card)] text-[var(--foreground)] w-full max-w-4xl h-[75vh] rounded-3xl border border-[var(--border)] shadow-2xl relative overflow-hidden flex flex-col z-10 glass"
        >
          {/* Header */}
          <header className="p-6 border-b border-[var(--border)] flex items-center justify-between gap-4 shrink-0 bg-[var(--secondary)]/20">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-pink-500/10 text-pink-400 rounded-xl border border-pink-500/20">
                <FileText className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-xl font-bold flex items-center gap-2">
                  Tailored Cover Letter
                </h2>
                <p className="text-xs text-[var(--muted-foreground)] font-semibold mt-0.5">
                  Generated for <span className="text-pink-400">{jobTitle} @ {company}</span>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleCopy}
                className="bg-[var(--secondary)] hover:bg-[var(--border)] border border-[var(--border)] text-[var(--foreground)] px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                {copied ? "Copied!" : "Copy Cover Letter"}
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

          {/* Content Panel */}
          <div className="flex-1 overflow-hidden flex flex-col">
            <div className="flex-1 overflow-y-auto p-6 font-mono text-sm leading-relaxed space-y-0.5 bg-[var(--background)]/20 whitespace-pre-wrap">
              {coverLetter}
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
