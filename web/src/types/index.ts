export interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  date_posted: string;
  salary: string;
  description: string;
  site: string;
  score: number;
  verdict: string;
  reason: string;
}

export interface Stats {
  total: number;
  strong: number;
  maybe: number;
  avg_score: number;
}

export interface KeywordAnalysis {
  found: string[];
  missing: string[];
}

export interface InterviewQuestion {
  question: string;
  type: "Technical" | "Behavioral" | "Experience";
  focus: string;
}
