"use client";

import React, { useEffect, useState, Suspense } from "react";
import { Upload, User, Settings, Loader2, Save, Key } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";

function ProfileContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session") || "00000000-0000-0000-0000-000000000000";

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  
  const [userEmail, setUserEmail] = useState("");
  const [targetRoles, setTargetRoles] = useState("");
  const [locations, setLocations] = useState("");
  const [geminiApiKey, setGeminiApiKey] = useState("");
  const [linkedinPassword, setLinkedinPassword] = useState("");
  const [resumeUrl, setResumeUrl] = useState<string | null>(null);

  useEffect(() => {
    async function loadProfile() {
      try {
        setLoading(true);
        setUserEmail("default@example.com");
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const headers = { "X-Session-ID": sessionId };

        // Load search preferences from backend API
        try {
          const settingsRes = await fetch(`${apiUrl}/settings`, { headers });
          if (settingsRes.ok) {
            const prefs = await settingsRes.json();
            setTargetRoles(prefs.target_roles?.join(", ") || "");
            setLocations(prefs.locations?.join(", ") || "");
          }
        } catch (err: any) {
          console.warn("Failed to load settings:", err.message || err);
        }

        // Fetch securely stored secrets from backend
        try {
          const secretsRes = await fetch(`${apiUrl}/secrets`, { headers });
          if (secretsRes.ok) {
            const secretKeys: string[] = await secretsRes.json();
            if (secretKeys.includes("gemini_api_key")) setGeminiApiKey("********");
            if (secretKeys.includes("linkedin_password")) setLinkedinPassword("********");
          }
        } catch (err: any) {
          console.warn("Failed to load secrets:", err.message || err);
        }

        // Check for uploaded resume via backend API
        try {
          const resumesRes = await fetch(`${apiUrl}/resumes`, { headers });
          if (resumesRes.ok) {
            const files = await resumesRes.json();
            if (files && files.length > 0) {
              setResumeUrl(files[0]);
            }
          }
        } catch (err: any) {
          console.warn("Failed to load resumes:", err.message || err);
        }

      } catch (error: any) {
        console.warn("Error loading profile:", error.message || error);
      } finally {
        setLoading(false);
      }
    }

    loadProfile();
  }, [router, sessionId]);

  const handleSavePreferences = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);

      const rolesArray = targetRoles.split(",").map(r => r.trim()).filter(Boolean);
      const locationsArray = locations.split(",").map(l => l.trim()).filter(Boolean);

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

      // Save public settings to Backend API
      const settingsRes = await fetch(`${apiUrl}/settings`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "X-Session-ID": sessionId
        },
        body: JSON.stringify({
          target_roles: rolesArray,
          locations: locationsArray
        })
      });

      if (!settingsRes.ok) {
        throw new Error("Failed to save settings to API");
      }

      // Save secrets to Backend API
      const headers = { 
        "Content-Type": "application/json",
        "X-Session-ID": sessionId
      };

      if (geminiApiKey && geminiApiKey !== "********") {
        await fetch(`${apiUrl}/secrets`, {
          method: "POST",
          headers,
          body: JSON.stringify({ secret_type: "gemini_api_key", value: geminiApiKey })
        });
      }

      if (linkedinPassword && linkedinPassword !== "********") {
        await fetch(`${apiUrl}/secrets`, {
          method: "POST",
          headers,
          body: JSON.stringify({ secret_type: "linkedin_password", value: linkedinPassword })
        });
      }

      alert("Preferences and secrets saved successfully!");
    } catch (error: any) {
      console.warn("Error saving preferences:", error.message || error);
      alert("Error saving preferences: " + (error.message || error));
    } finally {
      setSaving(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    try {
      setUploading(true);
      if (!e.target.files || e.target.files.length === 0) return;
      
      const file = e.target.files[0];
      const formData = new FormData();
      formData.append("file", file);

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/resumes`, {
        method: "POST",
        headers: { "X-Session-ID": sessionId },
        body: formData
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload failed");
      }

      setResumeUrl(file.name);
      alert("Resume uploaded successfully!");
    } catch (error: any) {
      console.warn("Error uploading file:", error.message || error);
      alert("Error uploading file: " + (error.message || error));
    } finally {
      setUploading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen text-[var(--foreground)] p-6 lg:p-10 relative z-10">
      <div className="bg-blobs" />
      
      <header className="max-w-4xl mx-auto mb-10 flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight flex items-center gap-3">
            <User className="text-indigo-500 w-8 h-8" />
            Profile & Settings
          </h1>
          <p className="text-[var(--muted-foreground)] mt-2">Manage your CV and job search preferences.</p>
        </div>
        <div className="flex gap-4">
          <button 
            onClick={() => router.push(`/?session=${sessionId}`)}
            className="glass px-4 py-2 rounded-xl text-sm font-bold hover:scale-105 transition-transform"
          >
            ← Back to Dashboard
          </button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto space-y-8">
        
        {/* Account Info */}
        <section className="glass p-8 rounded-2xl shadow-xl shadow-black/5">
          <h2 className="text-xl font-bold mb-4">Account Information</h2>
          <div className="bg-[var(--background)] p-4 rounded-xl border border-[var(--border)]">
            <p className="text-sm font-medium text-[var(--muted-foreground)]">Email</p>
            <p className="text-lg">{userEmail}</p>
          </div>
        </section>

        {/* Resume Upload */}
        <section className="glass p-8 rounded-2xl shadow-xl shadow-black/5">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Upload className="w-5 h-5 text-pink-500" />
            Base Resume (CV)
          </h2>
          <p className="text-sm text-[var(--muted-foreground)] mb-6">
            Upload your base resume. The AI will use this as the foundation to tailor your applications.
          </p>
          
          <div className="border-2 border-dashed border-[var(--border)] rounded-2xl p-10 text-center bg-[var(--background)] hover:bg-[var(--secondary)] transition-colors relative">
            <input 
              type="file" 
              accept=".pdf,.docx,.txt,.md"
              onChange={handleFileUpload}
              disabled={uploading}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />
            {uploading ? (
              <div className="flex flex-col items-center gap-2">
                <Loader2 className="w-8 h-8 animate-spin text-pink-500" />
                <p className="font-medium text-pink-500">Uploading...</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <Upload className="w-8 h-8 text-[var(--muted-foreground)]" />
                <p className="font-bold text-lg">
                  {resumeUrl ? "Update Resume" : "Click or drag file to upload"}
                </p>
                {resumeUrl && (
                  <p className="text-sm text-emerald-500 font-medium bg-emerald-500/10 px-3 py-1 rounded-full mt-2">
                    Current: {resumeUrl}
                  </p>
                )}
                <p className="text-xs text-[var(--muted-foreground)] mt-2">Supports PDF, DOCX, TXT</p>
              </div>
            )}
          </div>
        </section>

        {/* Search Preferences */}
        <section className="glass p-8 rounded-2xl shadow-xl shadow-black/5">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Settings className="w-5 h-5 text-emerald-500" />
            Job Search & Credentials
          </h2>
          <p className="text-sm text-[var(--muted-foreground)] mb-6">
            Configure the roles the AI Discovery Agent should look for, and manage your encrypted credentials.
          </p>

          <form onSubmit={handleSavePreferences} className="space-y-6">
            <div>
              <label className="block text-sm font-bold mb-2">Target Roles (comma-separated)</label>
              <input 
                type="text" 
                value={targetRoles}
                onChange={(e) => setTargetRoles(e.target.value)}
                placeholder="e.g. Software Engineer, Backend Developer, Full Stack"
                className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl py-3 px-4 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all"
              />
            </div>
            
            <div>
              <label className="block text-sm font-bold mb-2">Locations (comma-separated)</label>
              <input 
                type="text" 
                value={locations}
                onChange={(e) => setLocations(e.target.value)}
                placeholder="e.g. Remote, United States, Turkey, Istanbul"
                className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl py-3 px-4 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all"
              />
            </div>

            <div className="pt-4 border-t border-[var(--border)]">
              <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                <Key className="w-4 h-4 text-orange-500" />
                Encrypted Secrets
              </h3>
              <p className="text-xs text-[var(--muted-foreground)] mb-4">
                These values are encrypted in the database using AES-128 and are never visible in plain text on the frontend once saved.
              </p>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-bold mb-2">Gemini API Key</label>
                  <input 
                    type="password" 
                    value={geminiApiKey}
                    onChange={(e) => setGeminiApiKey(e.target.value)}
                    placeholder={geminiApiKey === "********" ? "********" : "Paste your API key here..."}
                    className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl py-3 px-4 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all"
                  />
                  <p className="text-[10px] text-[var(--muted-foreground)] mt-1 ml-1">
                    Used to power your automated job scoring and resume tailoring.
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-bold mb-2">LinkedIn Password</label>
                  <input 
                    type="password" 
                    value={linkedinPassword}
                    onChange={(e) => setLinkedinPassword(e.target.value)}
                    placeholder={linkedinPassword === "********" ? "********" : "Your LinkedIn password..."}
                    className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl py-3 px-4 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all"
                  />
                  <p className="text-[10px] text-[var(--muted-foreground)] mt-1 ml-1">
                    Used by the bot to log into LinkedIn for "Easy Apply".
                  </p>
                </div>
              </div>
            </div>

            <button 
              type="submit" 
              disabled={saving}
              className="bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white py-3 px-6 rounded-xl font-bold transition-all flex items-center gap-2"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {saving ? "Saving..." : "Save Preferences"}
            </button>
          </form>
        </section>

      </main>
    </div>
  );
}

export const runtime = "edge";

export default function ProfilePage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
      </div>
    }>
      <ProfileContent />
    </Suspense>
  );
}
