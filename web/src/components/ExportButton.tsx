"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { Download, Loader2 } from "lucide-react";

interface ExportButtonProps {
  /** Markdown content of the tailored resume */
  content: string;
  /** Used to name the downloaded file */
  jobTitle?: string;
  company?: string;
  className?: string;
}

/**
 * Exports a tailored resume as a styled PDF using the browser's print dialog.
 * This is a zero-cost, zero-server approach — everything runs client-side.
 *
 * For a more polished PDF layout, swap this with @react-pdf/renderer once
 * the dependency is installed (npm install @react-pdf/renderer).
 */
export function ExportButton({
  content,
  jobTitle = "Role",
  company = "Company",
  className = "",
}: ExportButtonProps) {
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      // Convert markdown to HTML using a simple renderer
      const html = markdownToHtml(content);

      const filename = `Resume_${company.replace(/\s+/g, "_")}_${jobTitle.replace(/\s+/g, "_")}`;

      // Open a new window, write a print-optimised HTML page, trigger print
      const printWindow = window.open("", "_blank");
      if (!printWindow) {
        alert("Please allow popups for PDF export.");
        return;
      }

      printWindow.document.write(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>${filename}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      font-size: 11pt;
      line-height: 1.6;
      color: #1a1a2e;
      background: #fff;
      padding: 40px 48px;
      max-width: 800px;
      margin: 0 auto;
    }

    h1 { font-size: 22pt; font-weight: 700; color: #1e1b4b; margin-bottom: 4px; }
    h2 {
      font-size: 12pt; font-weight: 600; color: #4338ca;
      text-transform: uppercase; letter-spacing: 0.05em;
      border-bottom: 2px solid #e0e7ff; padding-bottom: 4px;
      margin: 20px 0 10px;
    }
    h3 { font-size: 11pt; font-weight: 600; color: #1e1b4b; margin: 12px 0 4px; }
    p { margin-bottom: 8px; }
    ul { padding-left: 20px; margin-bottom: 10px; }
    li { margin-bottom: 3px; }
    strong { font-weight: 600; }
    em { font-style: italic; color: #4b5563; }
    a { color: #4338ca; text-decoration: none; }
    hr { border: none; border-top: 1px solid #e5e7eb; margin: 16px 0; }
    code {
      font-family: 'Courier New', monospace;
      background: #f3f4f6; padding: 1px 5px; border-radius: 4px;
      font-size: 9.5pt;
    }

    @media print {
      body { padding: 24px 32px; }
      @page { margin: 0.5in; }
    }
  </style>
</head>
<body>
${html}
<script>
  window.onload = function() {
    setTimeout(function() {
      window.print();
    }, 300);
  };
</script>
</body>
</html>`);
      printWindow.document.close();
    } finally {
      setExporting(false);
    }
  };

  return (
    <motion.button
      id="export-resume-btn"
      onClick={handleExport}
      disabled={exporting || !content}
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      className={`flex items-center gap-2 px-4 py-2 rounded-xl font-semibold text-sm
        bg-gradient-to-r from-indigo-600 to-purple-600 text-white
        shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40
        disabled:opacity-50 disabled:cursor-not-allowed
        transition-shadow ${className}`}
    >
      {exporting ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : (
        <Download className="w-4 h-4" />
      )}
      {exporting ? "Generating PDF…" : "Export as PDF"}
    </motion.button>
  );
}

// ── Minimal Markdown → HTML converter ────────────────────────────────────────

function markdownToHtml(markdown: string): string {
  return markdown
    // Headings
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    // Bold / italic
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // Horizontal rule
    .replace(/^---$/gm, "<hr />")
    // Unordered lists
    .replace(/^[*-] (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>[\s\S]+?<\/li>)\n(?!<li>)/g, "<ul>$1</ul>\n")
    // Inline code
    .replace(/`(.+?)`/g, "<code>$1</code>")
    // Line breaks → paragraphs
    .split("\n\n")
    .map((block) => {
      const trimmed = block.trim();
      if (!trimmed) return "";
      if (trimmed.startsWith("<h") || trimmed.startsWith("<ul") || trimmed.startsWith("<hr")) {
        return trimmed;
      }
      return `<p>${trimmed.replace(/\n/g, "<br/>")}</p>`;
    })
    .join("\n");
}
