import React from "react";
import { Briefcase, GraduationCap, Code, Clock, Star } from "lucide-react";
import { StructuredProfile } from "../types";

interface ProfileViewerProps {
  profile: StructuredProfile;
}

export function ProfileViewer({ profile }: ProfileViewerProps) {
  if (!profile) return null;

  return (
    <div className="space-y-6">
      {/* Header Info */}
      <div className="flex flex-col md:flex-row gap-6 p-6 rounded-2xl bg-indigo-500/5 border border-indigo-500/20">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <Star className="w-5 h-5 text-indigo-400" />
            <h3 className="text-xl font-bold text-[var(--foreground)]">{profile.desired_role || "Candidate Profile"}</h3>
          </div>
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
            <Clock className="w-4 h-4" />
            <span>{profile.years} Years of Experience</span>
          </div>
        </div>
      </div>

      {/* Skills */}
      {profile.skills && profile.skills.length > 0 && (
        <div>
          <h4 className="flex items-center gap-2 text-lg font-bold mb-3 text-[var(--foreground)]">
            <Code className="w-5 h-5 text-pink-400" />
            Core Skills
          </h4>
          <div className="flex flex-wrap gap-2">
            {profile.skills.map((skill, idx) => (
              <span
                key={idx}
                className="px-3 py-1 text-sm font-medium rounded-lg bg-[var(--card)] border border-[var(--border)] text-[var(--foreground)]"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Experience */}
      {profile.experience && profile.experience.length > 0 && (
        <div>
          <h4 className="flex items-center gap-2 text-lg font-bold mb-4 text-[var(--foreground)]">
            <Briefcase className="w-5 h-5 text-emerald-400" />
            Experience
          </h4>
          <div className="space-y-4">
            {profile.experience.map((exp, idx) => (
              <div key={idx} className="p-4 rounded-xl bg-[var(--card)] border border-[var(--border)] relative overflow-hidden group">
                <div className="absolute left-0 top-0 bottom-0 w-1 bg-emerald-500/20 group-hover:bg-emerald-500/50 transition-colors" />
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h5 className="font-bold text-[var(--foreground)]">{exp.title}</h5>
                    <p className="text-sm text-[var(--muted-foreground)]">{exp.company}</p>
                  </div>
                  <span className="text-xs font-medium text-[var(--muted-foreground)] bg-[var(--background)] px-2 py-1 rounded-md">
                    {exp.start_date} - {exp.end_date}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Education */}
      {profile.education && profile.education.length > 0 && (
        <div>
          <h4 className="flex items-center gap-2 text-lg font-bold mb-4 text-[var(--foreground)]">
            <GraduationCap className="w-5 h-5 text-blue-400" />
            Education
          </h4>
          <div className="space-y-4">
            {profile.education.map((edu, idx) => (
              <div key={idx} className="p-4 rounded-xl bg-[var(--card)] border border-[var(--border)] relative overflow-hidden group">
                <div className="absolute left-0 top-0 bottom-0 w-1 bg-blue-500/20 group-hover:bg-blue-500/50 transition-colors" />
                <div className="flex justify-between items-start">
                  <div>
                    <h5 className="font-bold text-[var(--foreground)]">{edu.degree}</h5>
                    <p className="text-sm text-[var(--muted-foreground)]">{edu.institution}</p>
                  </div>
                  <span className="text-xs font-medium text-[var(--muted-foreground)] bg-[var(--background)] px-2 py-1 rounded-md">
                    {edu.graduation_date}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
