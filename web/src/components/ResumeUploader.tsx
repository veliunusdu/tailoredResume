"use client";

import React, { useCallback, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, FileText, X, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { useSafeAuth } from "../hooks/useSafeAuth";
import { apiFetch } from "@/lib/api";

interface UploadedResume {
  id: string;
  filename: string;
  preview?: string;
  created_at: number;
}

interface ResumeUploaderProps {
  onUploadSuccess?: (resume: UploadedResume) => void;
  className?: string;
}

type UploadState = "idle" | "parsing" | "uploading" | "success" | "error";

export function ResumeUploader({ onUploadSuccess, className = "" }: ResumeUploaderProps) {
  const { getToken } = useSafeAuth();
  const [dragOver, setDragOver] = useState(false);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [successFile, setSuccessFile] = useState("");

  const extractText = async (file: File): Promise<string> => {
    const ext = file.name.split(".").pop()?.toLowerCase();

    if (ext === "md" || ext === "txt") {
      return await file.text();
    }

    if (ext === "pdf") {
      // Dynamic import to keep bundle light
      const pdfjsLib = await import("pdfjs-dist");
      pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`;

      const arrayBuffer = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
      let text = "";
      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const content = await page.getTextContent();
        // Cast via unknown to avoid strict TextItem vs TextMarkedContent union issue
        const items = content.items as unknown as Array<{ str?: string }>;
        text += items.map((item) => item.str ?? "").join(" ") + "\n";
      }
      return text.trim();


    }

    if (ext === "docx") {
      const mammoth = await import("mammoth");
      const arrayBuffer = await file.arrayBuffer();
      const result = await mammoth.extractRawText({ arrayBuffer });
      return result.value;
    }

    throw new Error(`Unsupported file type: .${ext}. Please upload .md, .txt, .pdf, or .docx`);
  };

  const handleFile = useCallback(
    async (file: File) => {
      const maxSizeMB = 5;
      if (file.size > maxSizeMB * 1024 * 1024) {
        setErrorMsg(`File is too large. Maximum size is ${maxSizeMB}MB.`);
        setUploadState("error");
        return;
      }

      try {
        setUploadState("parsing");
        setErrorMsg("");

        const content = await extractText(file);
        if (!content.trim()) {
          throw new Error("Could not extract text from file. Is it scanned/image-only?");
        }

        setUploadState("uploading");

        const params = new URLSearchParams({
          filename: file.name,
          content,
        });

        const res = await apiFetch(
          `/resumes?${params.toString()}`,
          { method: "POST" },
          getToken
        );

        if (!res.ok) {
          const err = await res.text();
          throw new Error(`Upload failed: ${err}`);
        }

        const data = await res.json();
        setUploadState("success");
        setSuccessFile(file.name);

        onUploadSuccess?.({
          id: data.resume_id,
          filename: file.name,
          created_at: Date.now() / 1000,
        });

        // Reset to idle after 3 seconds
        setTimeout(() => setUploadState("idle"), 3000);
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : "An unexpected error occurred.");
        setUploadState("error");
      }
    },
    [getToken, onUploadSuccess]
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      // Reset input so the same file can be re-uploaded
      e.target.value = "";
    },
    [handleFile]
  );

  const isProcessing = uploadState === "parsing" || uploadState === "uploading";

  return (
    <div className={className}>
      <label htmlFor="resume-upload-input">
        <motion.div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          animate={{
            borderColor: dragOver
              ? "rgba(99, 102, 241, 0.8)"
              : uploadState === "success"
              ? "rgba(16, 185, 129, 0.6)"
              : uploadState === "error"
              ? "rgba(239, 68, 68, 0.6)"
              : "rgba(255, 255, 255, 0.1)",
            scale: dragOver ? 1.01 : 1,
          }}
          transition={{ duration: 0.2 }}
          className="relative border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-colors glass"
          style={{ minHeight: "180px" }}
        >
          <AnimatePresence mode="wait">
            {uploadState === "idle" && (
              <motion.div
                key="idle"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="flex flex-col items-center gap-3"
              >
                <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 flex items-center justify-center">
                  <Upload className="w-7 h-7 text-indigo-400" />
                </div>
                <div>
                  <p className="font-semibold text-[var(--foreground)]">
                    Drop your resume here
                  </p>
                  <p className="text-sm text-[var(--muted-foreground)] mt-1">
                    or click to browse · PDF, DOCX, MD, TXT · Max 5MB
                  </p>
                </div>
              </motion.div>
            )}

            {isProcessing && (
              <motion.div
                key="processing"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center gap-3"
              >
                <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
                <p className="font-medium text-[var(--foreground)]">
                  {uploadState === "parsing" ? "Extracting text…" : "Uploading resume…"}
                </p>
              </motion.div>
            )}

            {uploadState === "success" && (
              <motion.div
                key="success"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center gap-3"
              >
                <CheckCircle2 className="w-10 h-10 text-emerald-400" />
                <div>
                  <p className="font-semibold text-emerald-400">Resume uploaded!</p>
                  <p className="text-sm text-[var(--muted-foreground)] mt-1">{successFile}</p>
                </div>
              </motion.div>
            )}

            {uploadState === "error" && (
              <motion.div
                key="error"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center gap-3"
              >
                <AlertCircle className="w-10 h-10 text-red-400" />
                <div>
                  <p className="font-semibold text-red-400">Upload failed</p>
                  <p className="text-sm text-[var(--muted-foreground)] mt-1 max-w-xs mx-auto">
                    {errorMsg}
                  </p>
                </div>
                <button
                  onClick={(e) => { e.preventDefault(); setUploadState("idle"); }}
                  className="text-xs text-indigo-400 hover:underline flex items-center gap-1"
                >
                  <X className="w-3 h-3" /> Try again
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </label>

      <input
        id="resume-upload-input"
        type="file"
        accept=".md,.txt,.pdf,.docx"
        className="sr-only"
        onChange={onFileInput}
        disabled={isProcessing}
      />
    </div>
  );
}
