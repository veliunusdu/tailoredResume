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
  tags?: string[];
  score: number;
  verdict: string;
  reason: string;
  status: string;
  tailored_resume?: string;
  cover_letter?: string;
  interview_questions?: InterviewQuestion[];
  required_skills?: string[];
  missing_skills?: string[];
  found_skills?: string[];
  skill_match_score?: number;
}

export interface Stats {
  total: number;
  strong: number;
  maybe: number;
  avg_score: number;
  last_discovery?: {
    run_id: string;
    raw_scraped_count: number;
    filtered_count: number;
    inserted_count: number;
    scored_count: number;
    strong_count: number;
    maybe_count: number;
    failed_count: number;
    status: "completed" | "failed";
    timestamp: number;
  };
}

export interface SourceAnalytics {
  board: string;
  total_raw: number;
  total_filtered: number;
  total_inserted: number;
  db_total: number;
  scored_count: number;
  strong_matches: number;
  maybe_matches: number;
  no_matches: number;
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

export interface ExperienceItem {
  company: string;
  title: string;
  start_date: string;
  end_date: string;
  description: string[];
}

export interface EducationItem {
  institution: string;
  degree: string;
  graduation_date: string;
}

export interface ProjectItem {
  name: string;
  description: string;
  skills_used: string[];
}

export interface StructuredProfile {
  skills: string[];
  experience: ExperienceItem[];
  education: EducationItem[];
  projects: ProjectItem[];
  years: number;
  desired_role: string;
}

export interface Resume {
  id: string;
  user_id?: string;
  filename: string;
  storage_path?: string;
  created_at: number;
  preview?: string;
  content?: string;
  structured_data?: StructuredProfile;
}

export interface SearchQuery {
  query: string;
  tier: 1 | 2 | 3;
}

export interface SearchLocation {
  location: string;
  remote: boolean;
}

export interface SearchConfig {
  queries: SearchQuery[];
  locations: SearchLocation[];
  boards: string[];
  exclude_titles: string[];
  seniority_levels: string[];
  profile_notes: string;
  results_per_site: number;
  hours_old: number;
}

export interface TaskProgress {
  task_id: string;
  status: string;
  message: string;
  progress: number;
}

export interface ApplyAttempt {
  id: string;
  status: string;
  error_msg?: string;
}
