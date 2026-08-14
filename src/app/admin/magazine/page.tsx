"use client";

import * as React from "react";
import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import type { MagazineIssue, User } from "@/lib/types";
import { ErrorState } from "@/components/shared";

export default function AdminMagazinePage() {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [issues, setIssues] = useState<MagazineIssue[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Upload Form State
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [magazineType, setMagazineType] = useState("monthly");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Replace PDF Modal State
  const [replaceIssue, setReplaceIssue] = useState<MagazineIssue | null>(null);
  const [replaceFile, setReplaceFile] = useState<File | null>(null);
  const [replacing, setReplacing] = useState(false);
  const [replaceError, setReplaceError] = useState<string | null>(null);
  const replaceFileInputRef = useRef<HTMLInputElement>(null);

  // Delete State
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const loadIssues = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.adminListMagazines();
      setIssues(data);
    } catch (err: any) {
      console.error("Failed to load magazines:", err);
      setError(err?.message || "Failed to query magazine issues from API.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    api.getCurrentUser().then((u) => {
      setCurrentUser(u);
      setAuthChecked(true);
      if (u && u.role?.toUpperCase() === "SUPER_ADMIN") {
        loadIssues();
      }
    });

    const interval = setInterval(() => {
      api.adminListMagazines().then(setIssues).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  if (authChecked && currentUser && currentUser.role?.toUpperCase() !== "SUPER_ADMIN") {
    return (
      <ErrorState
        title="Permission Denied"
        message="You do not have Super Administrator permissions required to upload or delete magazine issues."
        onRetry={() => (window.location.href = "/admin")}
      />
    );
  }

  const handleOpenUpload = () => {
    setTitle("");
    setDescription("");
    setYear(new Date().getFullYear());
    setMagazineType("monthly");
    setFile(null);
    setUploadError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setIsUploadOpen(true);
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !file) {
      setUploadError("Please provide an Issue Title and select a PDF file.");
      return;
    }

    setUploading(true);
    setUploadError(null);

    try {
      const formData = new FormData();
      formData.append("title", title.trim());
      formData.append("description", description.trim());
      formData.append("publication_year", String(year));
      formData.append("magazine_type", magazineType);
      formData.append("file", file);

      await api.adminUploadMagazine(formData);
      setIsUploadOpen(false);
      loadIssues();
    } catch (err: any) {
      console.error("Upload failure:", err);
      setUploadError(err?.message || "Failed to upload magazine PDF.");
    } finally {
      setUploading(false);
    }
  };

  const handleReplaceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replaceIssue || !replaceFile) {
      setReplaceError("Please select a new PDF file.");
      return;
    }

    setReplacing(true);
    setReplaceError(null);

    try {
      const formData = new FormData();
      formData.append("file", replaceFile);

      await api.adminReplaceMagazinePdf(replaceIssue.id, formData);
      setReplaceIssue(null);
      setReplaceFile(null);
      loadIssues();
    } catch (err: any) {
      console.error("Replace failure:", err);
      setReplaceError(err?.message || "Failed to replace magazine PDF.");
    } finally {
      setReplacing(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.adminDeleteMagazine(id);
      loadIssues();
    } catch (err: any) {
      console.error("Delete failure:", err);
    } finally {
      setConfirmDeleteId(null);
    }
  };

  return (
    <div className="space-y-6 relative min-h-[80vh]">
      {/* Header */}
      <div className="flex justify-between items-end border-b border-line pb-4">
        <div>
          <p className="font-util text-eyebrow text-ink-soft uppercase tracking-wider">
            Publication Management
          </p>
          <h1 className="font-display text-h2 font-semibold text-ink mt-1">
            SIET Magazine & Newsletters
          </h1>
        </div>
        <button
          onClick={handleOpenUpload}
          className="font-util text-eyebrow uppercase tracking-wider text-paper bg-ink hover:bg-accent border border-ink transition-colors px-4 py-2 cursor-pointer"
        >
          + Upload New PDF Issue
        </button>
      </div>

      {/* Issues Table */}
      <div className="border border-line bg-paper">
        {loading && issues.length === 0 ? (
          <div className="p-8 text-center font-display text-xs italic text-ink-soft">
            Querying magazine issues from repository...
          </div>
        ) : issues.length > 0 ? (
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-line bg-paper-2 font-util text-[10px] text-ink-soft uppercase tracking-wider">
                <th className="p-4 font-semibold">Cover</th>
                <th className="p-4 font-semibold">Title & Details</th>
                <th className="p-4 font-semibold">Status</th>
                <th className="p-4 font-semibold">Pages</th>
                <th className="p-4 font-semibold">Date</th>
                <th className="p-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {issues.map((issue) => (
                <tr key={issue.id} className="hover:bg-paper-2 transition-colors">
                  {/* Cover */}
                  <td className="p-4 w-16">
                    {issue.coverImageUrl ? (
                      <img
                        src={issue.coverImageUrl}
                        alt={issue.title}
                        className="w-12 h-16 object-cover border border-line shadow-xs bg-paper-3"
                      />
                    ) : (
                      <div className="w-12 h-16 bg-paper-3 border border-line flex items-center justify-center font-util text-[8px] text-ink-soft text-center p-1 uppercase">
                        No Cover
                      </div>
                    )}
                  </td>

                  {/* Title */}
                  <td className="p-4 max-w-sm">
                    <a
                      href={`/magazine/${issue.slug}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-display font-medium text-ink hover:text-accent hover:underline leading-snug block"
                    >
                      {issue.title}
                    </a>
                    {issue.description && (
                      <p className="font-body text-[11px] text-ink-soft line-clamp-1 mt-0.5">
                        {issue.description}
                      </p>
                    )}
                    <span className="inline-block mt-1 font-util text-[9px] text-ink-soft uppercase tracking-wider bg-paper-3 px-1.5 py-0.5 border border-line">
                      {issue.type} · {issue.year}
                    </span>
                  </td>

                  {/* Status */}
                  <td className="p-4 font-util">
                    {issue.status === "processing" ? (
                      <span className="inline-flex items-center gap-1.5 text-[10px] text-amber-700 bg-amber-50 px-2 py-0.5 border border-amber-200 uppercase tracking-wider font-semibold animate-pulse">
                        <span className="w-1.5 h-1.5 bg-amber-500 rounded-full" />
                        Processing...
                      </span>
                    ) : issue.status === "published" ? (
                      <span className="inline-flex items-center gap-1.5 text-[10px] text-emerald-700 bg-emerald-50 px-2 py-0.5 border border-emerald-200 uppercase tracking-wider font-semibold">
                        <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />
                        Published
                      </span>
                    ) : (
                      <span
                        title={issue.failureReason || "Processing failed"}
                        className="inline-flex items-center gap-1.5 text-[10px] text-rose-700 bg-rose-50 px-2 py-0.5 border border-rose-200 uppercase tracking-wider font-semibold cursor-help"
                      >
                        <span className="w-1.5 h-1.5 bg-rose-500 rounded-full" />
                        Failed
                      </span>
                    )}
                  </td>

                  {/* Page Count */}
                  <td className="p-4 font-sans text-ink-soft">
                    {(issue.pageCount || 0) > 0 ? `${issue.pageCount} pages` : "-"}
                  </td>

                  {/* Date */}
                  <td className="p-4 font-util text-ink-soft text-[11px]">
                    {new Date(issue.issueDate || Date.now()).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </td>

                  {/* Actions */}
                  <td className="p-4 text-right space-x-3">
                    {confirmDeleteId === issue.id ? (
                      <span className="font-util text-[10px] uppercase tracking-wider text-accent space-x-2">
                        <span>Confirm?</span>
                        <button
                          onClick={() => handleDelete(issue.id)}
                          className="underline hover:text-ink cursor-pointer font-bold"
                        >
                          Yes
                        </button>
                        <span className="text-line">/</span>
                        <button
                          onClick={() => setConfirmDeleteId(null)}
                          className="underline hover:text-ink cursor-pointer"
                        >
                          Cancel
                        </button>
                      </span>
                    ) : (
                      <>
                        <button
                          onClick={() => {
                            setReplaceIssue(issue);
                            setReplaceFile(null);
                            setReplaceError(null);
                          }}
                          className="font-util text-[10px] uppercase tracking-wider hover:text-accent cursor-pointer underline"
                        >
                          Replace PDF
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(issue.id)}
                          className="font-util text-[10px] uppercase tracking-wider text-accent hover:text-ink cursor-pointer underline"
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="p-12 text-center space-y-3">
            <p className="font-display text-sm text-ink font-medium">No magazine issues uploaded yet.</p>
            <p className="font-body text-xs text-ink-soft max-w-sm mx-auto">
              Click &quot;Upload New PDF Issue&quot; above to publish your first college tech digest or newsletter PDF.
            </p>
          </div>
        )}
      </div>

      {/* Upload Modal Drawer */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 bg-paper/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-lg border border-line bg-paper-2 p-6 space-y-5 shadow-lg">
            <div className="flex justify-between items-center border-b border-line pb-3">
              <h2 className="font-display text-body font-semibold text-ink">
                Upload New Magazine PDF Issue
              </h2>
              <button
                onClick={() => setIsUploadOpen(false)}
                className="font-util text-eyebrow text-ink-soft hover:text-ink uppercase tracking-wider text-xs"
              >
                [×]
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="space-y-4 text-xs">
              {/* Title */}
              <div className="space-y-1">
                <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                  Issue Title *
                </label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. SIET Tech Digest — August 2026 Edition"
                  className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink"
                />
              </div>

              {/* Description */}
              <div className="space-y-1">
                <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                  Description / Cover Note
                </label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Summary of featured articles, research spotlights..."
                  className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink resize-y"
                />
              </div>

              {/* Year & Type */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                    Publication Year
                  </label>
                  <input
                    type="number"
                    value={year}
                    onChange={(e) => setYear(Number(e.target.value))}
                    className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink"
                  />
                </div>
                <div className="space-y-1">
                  <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                    Issue Frequency
                  </label>
                  <select
                    value={magazineType}
                    onChange={(e) => setMagazineType(e.target.value)}
                    className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink font-util uppercase tracking-wider"
                  >
                    <option value="monthly">Monthly</option>
                    <option value="quarterly">Quarterly</option>
                    <option value="annual">Annual</option>
                    <option value="special">Special Edition</option>
                  </select>
                </div>
              </div>

              {/* PDF File Upload */}
              <div className="space-y-1.5 border border-dashed border-line p-4 bg-paper text-center">
                <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider mb-1">
                  PDF Document File *
                </label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf"
                  required
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="w-full text-xs font-sans text-ink cursor-pointer"
                />
                <p className="font-util text-[9px] text-ink-soft uppercase tracking-wider mt-1">
                  Pages will be automatically extracted into crisp images &amp; searchable text.
                </p>
              </div>

              {/* Error */}
              {uploadError && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 font-util text-[10px] uppercase tracking-wider">
                  {uploadError}
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3 pt-3 border-t border-line">
                <button
                  type="submit"
                  disabled={uploading}
                  className="flex-1 font-util text-eyebrow uppercase tracking-wider text-paper bg-ink hover:bg-accent border border-ink py-2.5 cursor-pointer disabled:opacity-50"
                >
                  {uploading ? "Uploading & Processing..." : "Start PDF Processing"}
                </button>
                <button
                  type="button"
                  onClick={() => setIsUploadOpen(false)}
                  className="px-4 font-util text-eyebrow uppercase tracking-wider text-ink border border-line hover:bg-paper py-2.5 cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Replace PDF Modal */}
      {replaceIssue && (
        <div className="fixed inset-0 z-50 bg-paper/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-md border border-line bg-paper-2 p-6 space-y-4 shadow-lg">
            <div className="flex justify-between items-center border-b border-line pb-3">
              <div>
                <p className="font-util text-[9px] text-ink-soft uppercase tracking-wider">
                  Re-process Existing Issue
                </p>
                <h3 className="font-display text-sm font-semibold text-ink">
                  Replace PDF for &ldquo;{replaceIssue.title}&rdquo;
                </h3>
              </div>
              <button
                onClick={() => setReplaceIssue(null)}
                className="font-util text-eyebrow text-ink-soft hover:text-ink uppercase tracking-wider text-xs"
              >
                [×]
              </button>
            </div>

            <form onSubmit={handleReplaceSubmit} className="space-y-4 text-xs">
              <p className="font-body text-xs text-ink-soft">
                Uploading a new PDF will replace the rendered page images and re-generate the table of contents.
                The URL slug (<code className="font-mono text-ink">{replaceIssue.slug}</code>) will stay identical.
              </p>

              <div className="space-y-1.5 border border-dashed border-line p-4 bg-paper text-center">
                <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider mb-1">
                  Select New PDF File *
                </label>
                <input
                  ref={replaceFileInputRef}
                  type="file"
                  accept="application/pdf"
                  required
                  onChange={(e) => setReplaceFile(e.target.files?.[0] || null)}
                  className="w-full text-xs font-sans text-ink cursor-pointer"
                />
              </div>

              {replaceError && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 font-util text-[10px] uppercase tracking-wider">
                  {replaceError}
                </div>
              )}

              <div className="flex gap-3 pt-2 border-t border-line">
                <button
                  type="submit"
                  disabled={replacing}
                  className="flex-1 font-util text-eyebrow uppercase tracking-wider text-paper bg-ink hover:bg-accent border border-ink py-2.5 cursor-pointer disabled:opacity-50"
                >
                  {replacing ? "Re-processing PDF..." : "Replace & Re-process"}
                </button>
                <button
                  type="button"
                  onClick={() => setReplaceIssue(null)}
                  className="px-4 font-util text-eyebrow uppercase tracking-wider text-ink border border-line hover:bg-paper py-2.5 cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
