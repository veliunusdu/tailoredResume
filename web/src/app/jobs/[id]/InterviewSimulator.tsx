"use client";

import { useState, useEffect } from "react";
import { useSafeAuth } from "@/hooks/useSafeAuth";
import { apiGet, apiPost } from "@/lib/api";
import { Loader2, MessageSquare, PlayCircle, Send, CheckCircle2 } from "lucide-react";
import { InterviewQuestion } from "@/types";
import { getErrorMessage } from "@/utils/errors";

interface InterviewAnswerGrade {
  score: number;
  feedback: string;
  ideal_points: string[];
}

export function InterviewSimulator({ jobId }: { jobId: string }) {
  const { getToken } = useSafeAuth();
  const [questions, setQuestions] = useState<InterviewQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [activeQuestion, setActiveQuestion] = useState<number>(0);
  const [answer, setAnswer] = useState("");
  const [grading, setGrading] = useState(false);
  const [grades, setGrades] = useState<Record<number, InterviewAnswerGrade>>({});

  useEffect(() => {
    async function fetchQuestions() {
      try {
        const data = await apiGet<InterviewQuestion[]>(`/jobs/${jobId}/interview-questions`, getToken);
        setQuestions(data);
      } catch (error: unknown) {
        setError(getErrorMessage(error, "Failed to generate interview questions."));
      } finally {
        setLoading(false);
      }
    }
    fetchQuestions();
  }, [jobId, getToken]);

  const handleGrade = async () => {
    if (!answer.trim()) return;
    setGrading(true);
    try {
      const result = await apiPost<InterviewAnswerGrade>(
        `/jobs/${jobId}/interview/grade`,
        { question: questions[activeQuestion].question, answer },
        getToken
      );
      setGrades((prev) => ({ ...prev, [activeQuestion]: result }));
    } catch (error: unknown) {
      console.error(getErrorMessage(error));
      alert("Failed to grade answer.");
    } finally {
      setGrading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6 flex flex-col items-center justify-center min-h-[300px]">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mb-4" />
        <p className="text-sm text-[var(--muted-foreground)] font-medium">Generating Tailored Questions...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-[var(--card)] border border-red-900/50 rounded-2xl p-6 text-center">
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  if (questions.length === 0) return null;

  const currentQ = questions[activeQuestion];
  const currentGrade = grades[activeQuestion];

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl overflow-hidden flex flex-col md:flex-row">
      {/* Sidebar: Question List */}
      <div className="w-full md:w-1/3 border-b md:border-b-0 md:border-r border-[var(--border)] bg-[var(--background)]/50">
        <div className="p-4 border-b border-[var(--border)]">
          <h3 className="text-sm font-bold text-[var(--foreground)] flex items-center gap-2 uppercase tracking-wider">
            <MessageSquare className="w-4 h-4 text-indigo-400" />
            Interview Simulator
          </h3>
        </div>
        <div className="p-2 space-y-1">
          {questions.map((q, idx) => {
            const isActive = activeQuestion === idx;
            const isGraded = !!grades[idx];
            return (
              <button
                key={idx}
                onClick={() => setActiveQuestion(idx)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all flex items-center justify-between ${
                  isActive
                    ? "bg-indigo-500/10 text-indigo-400 font-bold"
                    : "text-[var(--muted-foreground)] hover:bg-[var(--border)]/50 hover:text-[var(--foreground)]"
                }`}
              >
                <span className="truncate pr-2">Q{idx + 1}. {q.type}</span>
                {isGraded ? <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" /> : <PlayCircle className="w-4 h-4 opacity-50 shrink-0" />}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Panel */}
      <div className="w-full md:w-2/3 p-6 flex flex-col">
        <div className="mb-6">
          <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 mb-2 block">{currentQ.type} Question</span>
          <h2 className="text-lg font-bold text-[var(--foreground)] leading-snug">{currentQ.question}</h2>
          <p className="text-xs text-[var(--muted-foreground)] mt-2 italic border-l-2 border-[var(--border)] pl-2">
            Focus: {currentQ.focus}
          </p>
        </div>

        {!currentGrade ? (
          <div className="flex-1 flex flex-col">
            <textarea
              className="w-full flex-1 min-h-[150px] bg-[var(--background)] border border-[var(--border)] rounded-xl p-4 text-sm text-[var(--foreground)] focus:outline-none focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/20 transition-all resize-none mb-4 placeholder:text-[var(--muted-foreground)]/50"
              placeholder="Type or paste your answer here..."
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
            />
            <button
              onClick={handleGrade}
              disabled={grading || !answer.trim()}
              className="flex items-center justify-center gap-2 w-full bg-indigo-500 hover:bg-indigo-600 text-white py-3 rounded-xl font-bold transition-all disabled:opacity-50"
            >
              {grading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
              {grading ? "AI is Grading..." : "Submit Answer"}
            </button>
          </div>
        ) : (
          <div className="flex-1 space-y-6 animate-in fade-in zoom-in-95 duration-300">
            <div className="p-4 bg-[var(--background)] border border-[var(--border)] rounded-xl">
              <h4 className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider mb-2">Your Answer</h4>
              <p className="text-sm text-[var(--foreground)] whitespace-pre-wrap">{answer}</p>
            </div>

            <div className="p-5 bg-indigo-500/5 border border-indigo-500/20 rounded-xl space-y-4">
              <div className="flex items-center gap-4 border-b border-indigo-500/10 pb-4">
                <div className={`text-3xl font-black ${currentGrade.score >= 8 ? 'text-emerald-500' : currentGrade.score >= 5 ? 'text-amber-500' : 'text-rose-500'}`}>
                  {currentGrade.score}/10
                </div>
                <div className="text-sm text-[var(--foreground)] font-medium leading-relaxed">
                  {currentGrade.feedback}
                </div>
              </div>

              <div>
                <h4 className="text-xs font-bold text-indigo-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4" /> Ideal Points
                </h4>
                <ul className="space-y-2">
                  {currentGrade.ideal_points.map((pt, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-[var(--muted-foreground)]">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 shrink-0" />
                      {pt}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <button
              onClick={() => {
                setAnswer("");
                setGrades((prev) => {
                  const newGrades = { ...prev };
                  delete newGrades[activeQuestion];
                  return newGrades;
                });
              }}
              className="w-full py-3 bg-[var(--background)] border border-[var(--border)] rounded-xl text-sm font-bold text-[var(--foreground)] hover:bg-[var(--border)] transition-all"
            >
              Try Again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
