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

export interface DiscoveryStats {
  raw_scraped_count: number;
  filtered_count: number;
  scored_count: number;
  strong_count: number;
  maybe_count: number;
  timestamp: number;
}

export interface Stats {
  total: number;
  strong: number;
  maybe: number;
  avg_score: number;
  last_discovery?: DiscoveryStats | null;
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
