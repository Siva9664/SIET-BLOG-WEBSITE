"use client";

import * as React from "react";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { User, MagazineIssue } from "@/lib/types";
import { ErrorState } from "@/components/shared";

interface GalleryItem {
  id: string;
  file?: File | null;
  previewUrl: string;
  url?: string;
  note?: string;
  caption: string;
}

interface EventMagazine {
  id: string;
  title: string;
  slug: string;
  description?: string;
  eventName?: string;
  eventDate?: string;
  year?: number;
  type?: string;
  status: string;
  isFeatured?: boolean;
  featuredUntil?: string;
  pageCount?: number;
  pdfUrl?: string;
  coverImageUrl?: string;
  coverPages?: { url: string; caption?: string }[];
  bodyPages?: { url: string; caption?: string; html?: string }[];
  galleryImages?: { url: string; caption?: string }[];
  failureReason?: string;
  issueDate?: string;
  processedAt?: string;
  publishedAt?: string;
  createdAt?: string;
}

export default function AdminMagazinePage() {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [issues, setIssues] = useState<EventMagazine[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Modal State
  const [uploadMode, setUploadMode] = useState<"pdf" | "event">("event");
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  // Form Fields - Minimum Inputs for AI
  const [eventName, setEventName] = useState("");
  const [eventDate, setEventDate] = useState(new Date().toISOString().split("T")[0]);
  const [eventFile, setEventFile] = useState<File | null>(null);
  const [useManualNotes, setUseManualNotes] = useState(false);
  const [rawNotes, setRawNotes] = useState("");

  // Auto-Filled Fields
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [magazineType, setMagazineType] = useState("special");
  const [tocEntry, setTocEntry] = useState("");

  // One-Click AI Auto-Generate State
  const [aiAutoGenerating, setAiAutoGenerating] = useState(false);
  const [aiSuccessMessage, setAiSuccessMessage] = useState<string | null>(null);

  // Section 2 Mode & Article Preview
  const [section2Mode, setSection2Mode] = useState<"images" | "ai_article">("ai_article");
  const [aiGeneratedArticle, setAiGeneratedArticle] = useState<{ headline: string; html: string } | null>(null);

  // Files & Gallery State
  const [coverFiles, setCoverFiles] = useState<File[]>([]);
  const [bodyFiles, setBodyFiles] = useState<File[]>([]);
  const [galleryItems, setGalleryItems] = useState<GalleryItem[]>([]);
  const [pdfFile, setPdfFile] = useState<File | null>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const loadIssues = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.adminListMagazines();
      setIssues(Array.isArray(data) ? (data as any) : []);
    } catch (err: any) {
      console.error("Failed to load magazines:", err);
      setIssues([]);
      setError("Could not load magazines. Please refresh or check your connection.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    api.getCurrentUser().then((u) => {
      setCurrentUser(u);
      setAuthChecked(true);
      if (u && ["SUPER_ADMIN", "ADMIN", "admin"].includes(u.role)) {
        loadIssues();
      }
    });

    const interval = setInterval(() => {
      api.adminListMagazines().then((data) => {
        if (Array.isArray(data)) setIssues(data as any);
      }).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  if (authChecked && currentUser && !["SUPER_ADMIN", "ADMIN", "admin"].includes(currentUser.role)) {
    return (
      <ErrorState
        title="Permission Denied"
        message="You do not have Administrator permissions required to manage magazines."
        onRetry={() => (window.location.href = "/admin")}
      />
    );
  }

  const handleOpenUpload = (mode: "event" | "pdf" = "event") => {
    setUploadMode(mode);
    setEventName("");
    setEventDate(new Date().toISOString().split("T")[0]);
    setEventFile(null);
    setUseManualNotes(false);
    setRawNotes("");
    setTitle("");
    setDescription("");
    setYear(new Date().getFullYear());
    setMagazineType("special");
    setTocEntry("");
    setSection2Mode("ai_article");
    setAiGeneratedArticle(null);
    setAiSuccessMessage(null);
    setCoverFiles([]);
    setBodyFiles([]);
    setGalleryItems([]);
    setPdfFile(null);
    setUploadError(null);
    setIsUploadOpen(true);
  };

  // ─── ONE-CLICK AI AUTO-FILL HANDLER (FILE & MANUAL) ───────────────────────
  const handleOneClickAutoGenerate = async () => {
    if (!useManualNotes && !eventFile) {
      if (!eventName.trim() && !rawNotes.trim()) {
        setUploadError("Please select an Event File (.docx, .pdf, .txt) to upload, or click 'Type notes instead'.");
        return;
      }
    }

    if (useManualNotes && !eventName.trim() && !rawNotes.trim()) {
      setUploadError("Please provide an Event Name or rough notes first.");
      return;
    }

    setAiAutoGenerating(true);
    setUploadError(null);
    setAiSuccessMessage(null);

    try {
      if (!useManualNotes && eventFile) {
        // Step 1: Extract content from file & feed into AI pipeline
        const formData = new FormData();
        formData.append("file", eventFile);
        if (eventName.trim()) formData.append("event_name", eventName.trim());
        if (eventDate) formData.append("event_date", eventDate);

        const res = await api.adminAutoGenerateFromFile(formData);

        // Step 4: Auto-suggest Event Name & Date if found in document
        if (res.detected_event_name) {
          setEventName(res.detected_event_name);
        }
        if (res.detected_event_date) {
          setEventDate(res.detected_event_date);
        }
        if (res.extracted_notes) {
          setRawNotes(res.extracted_notes);
        }

        // Step 2: Auto-fill fields from AI result
        setTitle(res.magazine_issue_title);
        setDescription(res.description);
        setSection2Mode("ai_article");
        setAiGeneratedArticle({
          headline: res.writeup_headline,
          html: res.writeup_html,
        });

        // Step 3: Handle images conditionally
        if (res.extracted_images && res.extracted_images.length > 0) {
          const extractedGallery: GalleryItem[] = res.extracted_images.map((img: any, idx: number) => ({
            id: img.id || `ext_${Date.now()}_${idx}`,
            file: null,
            previewUrl: img.url,
            url: img.url,
            note: "",
            caption: (res.captions && res.captions[idx]) || img.file_name || `Photo from ${res.detected_event_name || eventName}`,
          }));
          setGalleryItems(extractedGallery);
        } else {
          // If no images found, leave Section 3 empty and untouched
          if (galleryItems.length === 0) {
            setGalleryItems([]);
          }
        }

        setTocEntry(res.toc_summary);
        setAiSuccessMessage("✨ File analyzed & full magazine auto-filled! Review and edit anything below before publishing.");
      } else {
        // Fallback: Manual Notes Input
        if (!eventName.trim()) {
          setUploadError("Please provide an Event Name first.");
          setAiAutoGenerating(false);
          return;
        }
        if (!rawNotes.trim()) {
          setUploadError("Please provide raw notes about the event first.");
          setAiAutoGenerating(false);
          return;
        }

        const res = await api.adminAutoGenerateFullMagazine({
          event_name: eventName.trim(),
          event_date: eventDate,
          raw_notes: rawNotes.trim(),
          photo_count: galleryItems.length,
        });

        setTitle(res.magazine_issue_title);
        setDescription(res.description);
        setSection2Mode("ai_article");
        setAiGeneratedArticle({
          headline: res.writeup_headline,
          html: res.writeup_html,
        });

        if (galleryItems.length > 0 && res.captions && res.captions.length > 0) {
          const updated = galleryItems.map((g, idx) => ({
            ...g,
            caption: res.captions[idx] || g.caption || `Photo from ${eventName}`,
          }));
          setGalleryItems(updated);
        }

        setTocEntry(res.toc_summary);
        setAiSuccessMessage("✨ All fields auto-filled! Review and edit anything below before publishing.");
      }
    } catch (err: any) {
      console.error("AI Auto-Fill Error:", err);
      setUploadError(err?.message || "File processing or AI generation failed. Click 'Type notes instead' to switch to manual mode.");
    } finally {
      setAiAutoGenerating(false);
    }
  };

  const handleGalleryFilesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const items: GalleryItem[] = files.map((f, idx) => ({
      id: `${Date.now()}_${idx}`,
      file: f,
      previewUrl: URL.createObjectURL(f),
      note: "",
      caption: "",
    }));
    setGalleryItems((prev) => [...prev, ...items]);
  };

  // Submit Handler
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploading(true);
    setUploadError(null);

    try {
      if (uploadMode === "pdf") {
        if (!title.trim() || !pdfFile) {
          throw new Error("Please provide a Title and select a PDF file.");
        }
        const formData = new FormData();
        formData.append("title", title.trim());
        formData.append("description", description.trim());
        formData.append("publication_year", String(year));
        formData.append("magazine_type", magazineType);
        if (eventName.trim()) formData.append("event_name", eventName.trim());
        if (eventDate) formData.append("event_date", eventDate);
        formData.append("file", pdfFile);

        await api.adminUploadMagazine(formData);
      } else {
        if (!eventName.trim() || !title.trim()) {
          throw new Error("Event Name and Magazine Title are required.");
        }

        // 1. Create event magazine draft with initial extracted gallery images
        const createFd = new FormData();
        createFd.append("event_name", eventName.trim());
        createFd.append("title", title.trim());
        createFd.append("description", description.trim());
        createFd.append("event_date", eventDate);
        createFd.append("publication_year", String(year));
        createFd.append("magazine_type", magazineType);

        // Include any extracted images already uploaded to server
        const extractedGallery = galleryItems
          .filter((item) => item.url && !item.file)
          .map((item) => ({ url: item.url, caption: item.caption }));

        if (extractedGallery.length > 0) {
          createFd.append("gallery_images_json", JSON.stringify(extractedGallery));
        }

        const res = await api.adminCreateEventMagazine(createFd);
        const magId = res.id;

        // 2. Upload Cover Pages
        if (coverFiles.length > 0) {
          const cFd = new FormData();
          coverFiles.forEach((f) => cFd.append("files", f));
          await api.adminUploadMagazineCover(magId, cFd);
        }

        // 3. Upload Body Pages
        if (section2Mode === "images" && bodyFiles.length > 0) {
          const bFd = new FormData();
          bodyFiles.forEach((f) => bFd.append("files", f));
          await api.adminUploadMagazineBody(magId, bFd);
        }

        // 4. Upload Newly Selected Local Gallery Photos
        const newGalleryFiles = galleryItems.filter((item) => item.file);
        if (newGalleryFiles.length > 0) {
          const gFd = new FormData();
          newGalleryFiles.forEach((item) => {
            if (item.file) gFd.append("files", item.file);
          });
          await api.adminUploadMagazineGallery(magId, gFd);
        }

        // 5. Publish
        await api.adminPublishMagazine(magId);
      }

      setIsUploadOpen(false);
      loadIssues();
    } catch (err: any) {
      console.error("Upload failure:", err);
      setUploadError(err?.message || "Failed to create magazine.");
    } finally {
      setUploading(false);
    }
  };

  const handleTogglePublish = async (issue: EventMagazine) => {
    try {
      if (issue.status === "published") {
        await api.adminUnpublishMagazine(issue.id);
      } else {
        await api.adminPublishMagazine(issue.id);
      }
      loadIssues();
    } catch (err: any) {
      console.error("Publish toggle error:", err);
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
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-line pb-4">
        <div>
          <p className="font-util text-eyebrow text-ink-soft uppercase tracking-wider">
            One-Click AI Publication Platform
          </p>
          <h1 className="font-display text-h2 font-semibold text-ink mt-1">
            SIET Event Magazines &amp; Newsletters
          </h1>
          <p className="font-body text-xs text-ink-soft mt-1">
            Give minimal event notes and click &quot;Auto-Generate with AI&quot; to auto-fill the full magazine.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => handleOpenUpload("event")}
            className="font-util text-eyebrow uppercase tracking-wider text-paper bg-accent hover:opacity-90 border border-accent transition-opacity px-4 py-2 cursor-pointer font-bold flex items-center gap-1.5 shadow-sm"
          >
            <span>✨</span> Create Event Magazine
          </button>
          <button
            onClick={() => handleOpenUpload("pdf")}
            className="font-util text-eyebrow uppercase tracking-wider text-ink border border-line hover:bg-paper-2 transition-colors px-4 py-2 cursor-pointer"
          >
            📄 Upload Full PDF
          </button>
        </div>
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
                <th className="p-4 font-semibold">Event &amp; Title</th>
                <th className="p-4 font-semibold">Priority / Status</th>
                <th className="p-4 font-semibold">Structure</th>
                <th className="p-4 font-semibold">Event Date</th>
                <th className="p-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {issues.map((issue) => (
                <tr key={issue.id} className="hover:bg-paper-2 transition-colors">
                  <td className="p-4 w-16">
                    {issue.coverImageUrl ? (
                      <img
                        src={issue.coverImageUrl}
                        alt={issue.title}
                        className="w-12 h-16 object-cover border border-line shadow-xs bg-paper-3"
                      />
                    ) : issue.coverPages && issue.coverPages.length > 0 ? (
                      <img
                        src={issue.coverPages[0].url}
                        alt={issue.title}
                        className="w-12 h-16 object-cover border border-line shadow-xs bg-paper-3"
                      />
                    ) : (
                      <div className="w-12 h-16 bg-paper-3 border border-line flex items-center justify-center font-util text-[8px] text-ink-soft text-center p-1 uppercase">
                        No Cover
                      </div>
                    )}
                  </td>

                  <td className="p-4 max-w-sm">
                    {issue.eventName && (
                      <span className="font-util text-[9px] uppercase tracking-wider text-accent font-bold block mb-0.5">
                        📍 {issue.eventName}
                      </span>
                    )}
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
                  </td>

                  <td className="p-4 font-util">
                    <div className="flex flex-col gap-1 items-start">
                      {issue.status === "published" ? (
                        <span className="inline-flex items-center gap-1.5 text-[10px] text-emerald-700 bg-emerald-50 px-2 py-0.5 border border-emerald-200 uppercase tracking-wider font-semibold">
                          <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />
                          Published
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-[10px] text-amber-700 bg-amber-50 px-2 py-0.5 border border-amber-200 uppercase tracking-wider font-semibold">
                          Draft
                        </span>
                      )}

                      {issue.isFeatured ? (
                        <span className="inline-flex items-center gap-1 text-[9px] text-blue-700 bg-blue-50 px-1.5 py-0.5 border border-blue-200 uppercase tracking-wider font-semibold">
                          ⭐ Priority (0-90 Days)
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[9px] text-slate-600 bg-slate-100 px-1.5 py-0.5 border border-slate-200 uppercase tracking-wider">
                          📦 Archived Feed
                        </span>
                      )}
                    </div>
                  </td>

                  <td className="p-4 font-sans text-ink-soft text-[11px]">
                    {issue.coverPages?.length || issue.bodyPages?.length || issue.galleryImages?.length ? (
                      <div className="space-y-0.5 font-util text-[9px] uppercase tracking-wider">
                        <div>Cover: {issue.coverPages?.length || 0} pgs</div>
                        <div>Body: {issue.bodyPages?.length || 0} pgs</div>
                        <div>Gallery: {issue.galleryImages?.length || 0} photos</div>
                      </div>
                    ) : (
                      <span>{issue.pageCount || 0} PDF pages</span>
                    )}
                  </td>

                  <td className="p-4 font-util text-ink-soft text-[11px]">
                    {new Date(issue.eventDate || issue.issueDate || issue.createdAt || Date.now()).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </td>

                  <td className="p-4 text-right space-x-2">
                    <button
                      onClick={() => handleTogglePublish(issue)}
                      className={`font-util text-[10px] uppercase tracking-wider px-2 py-1 border cursor-pointer ${
                        issue.status === "published"
                          ? "border-amber-300 text-amber-700 hover:bg-amber-50"
                          : "border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                      }`}
                    >
                      {issue.status === "published" ? "Unpublish" : "Publish Now"}
                    </button>

                    {confirmDeleteId === issue.id ? (
                      <span className="font-util text-[10px] uppercase tracking-wider text-accent space-x-1">
                        <span>Sure?</span>
                        <button
                          onClick={() => handleDelete(issue.id)}
                          className="underline hover:text-ink cursor-pointer font-bold"
                        >
                          Yes
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(null)}
                          className="underline hover:text-ink cursor-pointer"
                        >
                          No
                        </button>
                      </span>
                    ) : (
                      <button
                        onClick={() => setConfirmDeleteId(issue.id)}
                        className="font-util text-[10px] uppercase tracking-wider text-accent hover:text-ink cursor-pointer underline"
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="p-12 text-center space-y-3">
            <p className="font-display text-sm text-ink font-medium">No event magazines published yet.</p>
            <p className="font-body text-xs text-ink-soft max-w-sm mx-auto">
              Click &quot;Create Event Magazine&quot; to auto-fill title, writeups, and captions with AI.
            </p>
          </div>
        )}
      </div>

      {/* ONE-CLICK AI AUTO-FILL FORM MODAL */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 bg-paper/70 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
          <div className="w-full max-w-3xl border border-line bg-paper-2 p-6 space-y-6 shadow-xl my-8">
            {/* Header */}
            <div className="flex justify-between items-center border-b border-line pb-3">
              <div>
                <p className="font-util text-[9px] uppercase tracking-wider text-accent font-bold flex items-center gap-1">
                  <span>✨</span> {uploadMode === "event" ? "One-Click AI Content Auto-Fill" : "📄 PDF Document Upload"}
                </p>
                <h2 className="font-display text-body font-semibold text-ink">
                  {uploadMode === "event" ? "Create Event Magazine" : "Upload Single PDF Issue"}
                </h2>
              </div>
              <button
                onClick={() => setIsUploadOpen(false)}
                className="font-util text-eyebrow text-ink-soft hover:text-ink uppercase tracking-wider text-xs cursor-pointer"
              >
                [×]
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="space-y-5 text-xs">
              {uploadMode === "event" && (
                /* ─── STEP 1: ADMIN FILE UPLOAD & MINIMAL INPUT BOX ─────────────────────────────── */
                <div className="bg-paper p-4 border-2 border-accent/40 space-y-3 rounded-xs shadow-xs">
                  <div className="flex items-center justify-between border-b border-line pb-2">
                    <span className="font-util text-[10px] uppercase tracking-wider text-accent font-bold flex items-center gap-1.5">
                      <span>⚡</span> Step 1: Upload Event File or Provide Notes
                    </span>
                    <span className="font-util text-[9px] uppercase tracking-wider text-ink-soft">
                      Step 1 of 2
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                        Event Name <span className="text-[10px] font-normal text-ink-soft">(Optional - Auto-suggested)</span>
                      </label>
                      <input
                        type="text"
                        value={eventName}
                        onChange={(e) => setEventName(e.target.value)}
                        placeholder="e.g. Tech Fest 2026 / Alumni Meet"
                        className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink font-medium"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                        Event Date <span className="text-[10px] font-normal text-ink-soft">(Optional - Auto-suggested)</span>
                      </label>
                      <input
                        type="date"
                        value={eventDate}
                        onChange={(e) => setEventDate(e.target.value)}
                        className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink font-util"
                      />
                    </div>
                  </div>

                  {/* File Upload / Manual Notes Fallback */}
                  {!useManualNotes ? (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider font-bold">
                          Upload Event File * (.docx, .pdf, .txt)
                        </label>
                        <button
                          type="button"
                          onClick={() => setUseManualNotes(true)}
                          className="font-util text-[10px] uppercase tracking-wider text-accent hover:underline cursor-pointer font-bold"
                        >
                          Type notes instead
                        </button>
                      </div>
                      <div className="border border-dashed border-accent/50 p-4 bg-paper hover:bg-paper-2 transition-colors flex flex-col items-center justify-center gap-1 text-center relative rounded-xs">
                        <input
                          type="file"
                          accept=".docx,.doc,.pdf,.txt"
                          onChange={(e) => {
                            const f = e.target.files?.[0] || null;
                            setEventFile(f);
                            if (f) setUploadError(null);
                          }}
                          className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                        />
                        {eventFile ? (
                          <div className="flex items-center gap-2 font-util text-xs text-emerald-800 font-bold z-10">
                            <span>📄 {eventFile.name}</span>
                            <span className="text-[10px] font-normal text-ink-soft">({(eventFile.size / 1024).toFixed(1)} KB)</span>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setEventFile(null);
                              }}
                              className="text-accent hover:underline text-[10px] ml-2"
                            >
                              Change
                            </button>
                          </div>
                        ) : (
                          <div className="space-y-1 pointer-events-none">
                            <p className="font-util text-xs font-bold text-ink">
                              📁 Click or drag file here (.docx, .pdf, .txt)
                            </p>
                            <p className="font-body text-[10px] text-ink-soft">
                              Word docs, PDFs, or Text files (text &amp; embedded images are automatically extracted).
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider font-bold">
                          Rough Event Notes / Bullet Points *
                        </label>
                        <button
                          type="button"
                          onClick={() => setUseManualNotes(false)}
                          className="font-util text-[10px] uppercase tracking-wider text-accent hover:underline cursor-pointer font-bold"
                        >
                          Upload event file instead
                        </button>
                      </div>
                      <textarea
                        rows={3}
                        value={rawNotes}
                        onChange={(e) => setRawNotes(e.target.value)}
                        placeholder="Type rough notes (e.g. Dr. Sharma keynote, 200 students, robotics demo, hackathon winner announced)..."
                        className="w-full border border-line bg-paper-2 px-3 py-2 outline-none focus:border-ink resize-y font-sans text-xs"
                      />
                    </div>
                  )}

                  {/* ─── ONE-CLICK MAIN AI BUTTON ─────────────────────────────────── */}
                  <div className="pt-1">
                    <button
                      type="button"
                      onClick={handleOneClickAutoGenerate}
                      disabled={aiAutoGenerating}
                      className="w-full font-util text-xs uppercase tracking-wider text-paper bg-accent hover:opacity-95 border border-accent py-3 px-4 transition-all cursor-pointer font-bold flex items-center justify-center gap-2 shadow-md disabled:opacity-50"
                    >
                      {aiAutoGenerating ? (
                        <>
                          <span className="animate-spin">⏳</span>
                          <span>Reading file &amp; generating content...</span>
                        </>
                      ) : (
                        <>
                          <span>✨</span>
                          <span>Auto-Generate with AI (One-Click Auto-Fill)</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}

              {/* AI Success Banner */}
              {aiSuccessMessage && (
                <div className="p-3 bg-emerald-50 border border-emerald-300 text-emerald-800 font-util text-[10px] uppercase tracking-wider flex justify-between items-center font-bold">
                  <span>{aiSuccessMessage}</span>
                  <button
                    type="button"
                    onClick={() => setAiSuccessMessage(null)}
                    className="underline hover:no-underline cursor-pointer"
                  >
                    Dismiss
                  </button>
                </div>
              )}

              {/* ─── STEP 2: AUTO-FILLED EDITABLE FIELDS ─────────────────────────── */}
              <div className="space-y-4 pt-2">
                {uploadMode === "event" && (
                  <p className="font-util text-[9px] uppercase tracking-wider text-ink-soft border-b border-line pb-1">
                    Step 2: Review &amp; Edit Auto-Filled Form Fields
                  </p>
                )}

                {/* Title & TOC Summary */}
                <div className="space-y-1">
                  <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                    Magazine Issue Title *
                  </label>
                  <input
                    type="text"
                    required
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Auto-filled catchy magazine title"
                    className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink font-medium"
                  />
                  {tocEntry && (
                    <p className="font-util text-[10px] text-emerald-800 bg-emerald-50 border border-emerald-200 p-2 font-medium">
                      📌 Table of Contents Summary: &quot;{tocEntry}&quot;
                    </p>
                  )}
                </div>

                {/* Description / Event Overview */}
                <div className="space-y-1">
                  <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                    Description / Event Overview
                  </label>
                  <textarea
                    rows={3}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Auto-filled 3-4 sentence polished overview..."
                    className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink resize-y font-sans text-xs"
                  />
                </div>

                {/* Event Sections Upload / Article Review */}
                {uploadMode === "event" ? (
                  <div className="space-y-4 border-t border-b border-line py-4">
                    {/* Section 1: Cover Pages */}
                    <div className="border border-line p-3 bg-paper space-y-1">
                      <label className="block font-util text-[10px] text-ink uppercase tracking-wider font-bold">
                        1. Cover &amp; Intro Pages (First 2 Pages)
                      </label>
                      <input
                        type="file"
                        accept="image/*"
                        multiple
                        onChange={(e) => setCoverFiles(Array.from(e.target.files || []).slice(0, 2))}
                        className="w-full text-xs font-sans text-ink cursor-pointer"
                      />
                      {coverFiles.length > 0 && (
                        <p className="font-util text-[9px] text-emerald-700 font-bold mt-1">
                          ✓ {coverFiles.length} Cover Page image(s) selected
                        </p>
                      )}
                    </div>

                    {/* Section 2: Write-Up Article */}
                    <div className="border border-line p-3 bg-paper space-y-2">
                      <div className="flex items-center justify-between border-b border-line pb-1">
                        <label className="block font-util text-[10px] text-ink uppercase tracking-wider font-bold">
                          2. Event Write-Up &amp; Article Content
                        </label>
                        <div className="flex gap-1 font-util text-[9px] uppercase tracking-wider">
                          <button
                            type="button"
                            onClick={() => setSection2Mode("ai_article")}
                            className={`px-2 py-0.5 border cursor-pointer ${
                              section2Mode === "ai_article"
                                ? "bg-accent text-paper border-accent font-bold"
                                : "bg-paper text-ink border-line"
                            }`}
                          >
                            ✨ AI Article
                          </button>
                          <button
                            type="button"
                            onClick={() => setSection2Mode("images")}
                            className={`px-2 py-0.5 border cursor-pointer ${
                              section2Mode === "images"
                                ? "bg-ink text-paper border-ink font-bold"
                                : "bg-paper text-ink border-line"
                            }`}
                          >
                            📷 Upload Images
                          </button>
                        </div>
                      </div>

                      {section2Mode === "ai_article" && aiGeneratedArticle ? (
                        <div className="border border-emerald-300 bg-emerald-50/70 p-3 space-y-2">
                          <span className="font-util text-[9px] uppercase tracking-wider text-emerald-800 font-bold">
                            ✓ Auto-Generated Article (400-600 words)
                          </span>
                          <h4 className="font-display text-sm font-bold text-ink">{aiGeneratedArticle.headline}</h4>
                          <div
                            className="font-body text-xs text-ink-soft max-h-36 overflow-y-auto border-t border-emerald-200 pt-2 leading-relaxed"
                            dangerouslySetInnerHTML={{ __html: aiGeneratedArticle.html }}
                          />
                        </div>
                      ) : section2Mode === "images" ? (
                        <input
                          type="file"
                          accept="image/*"
                          multiple
                          onChange={(e) => setBodyFiles(Array.from(e.target.files || []))}
                          className="w-full text-xs font-sans text-ink cursor-pointer"
                        />
                      ) : (
                        <p className="font-body text-xs italic text-ink-soft">
                          Click &quot;Auto-Generate with AI&quot; above to build article content automatically.
                        </p>
                      )}
                    </div>

                    {/* Section 3: Photo Gallery */}
                    <div className="border border-line p-3 bg-paper space-y-3">
                      <label className="block font-util text-[10px] text-ink uppercase tracking-wider font-bold">
                        3. Event Photo Gallery &amp; Captions
                      </label>
                      <input
                        type="file"
                        accept="image/*"
                        multiple
                        onChange={handleGalleryFilesChange}
                        className="w-full text-xs font-sans text-ink cursor-pointer"
                      />

                      {galleryItems.length > 0 && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                          {galleryItems.map((item, idx) => (
                            <div key={item.id} className="flex gap-2 border border-line bg-paper-2 p-2">
                              <img
                                src={item.previewUrl}
                                alt={`Photo ${idx + 1}`}
                                className="w-14 h-14 object-cover border border-line flex-shrink-0 bg-paper-3"
                              />
                              <div className="flex-1 min-w-0">
                                <label className="block font-util text-[8px] uppercase text-ink-soft mb-0.5">
                                  Photo Caption ({idx + 1}):
                                </label>
                                <input
                                  type="text"
                                  value={item.caption}
                                  onChange={(e) => {
                                    const val = e.target.value;
                                    setGalleryItems((prev) =>
                                      prev.map((g) => (g.id === item.id ? { ...g, caption: val } : g))
                                    );
                                  }}
                                  placeholder="Auto-filled caption..."
                                  className="w-full border border-emerald-300 bg-emerald-50 px-2 py-1 text-[10px] font-sans text-emerald-900 outline-none"
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  /* PDF Mode File Input */
                  <div className="space-y-1.5 border border-dashed border-line p-4 bg-paper text-center">
                    <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider mb-1">
                      PDF Document File *
                    </label>
                    <input
                      type="file"
                      accept="application/pdf"
                      required
                      onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                      className="w-full text-xs font-sans text-ink cursor-pointer"
                    />
                  </div>
                )}

                {/* Error Banner */}
                {uploadError && (
                  <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 font-util text-[10px] uppercase tracking-wider flex justify-between items-center">
                    <span>⚠️ {uploadError}</span>
                    <button
                      type="button"
                      onClick={() => setUploadError(null)}
                      className="underline hover:no-underline cursor-pointer"
                    >
                      Dismiss
                    </button>
                  </div>
                )}

                {/* Submit Action */}
                <div className="flex gap-3 pt-3 border-t border-line">
                  <button
                    type="submit"
                    disabled={uploading}
                    className="flex-1 font-util text-eyebrow uppercase tracking-wider text-paper bg-accent hover:opacity-90 border border-accent py-3 cursor-pointer disabled:opacity-50 font-bold text-xs shadow-sm"
                  >
                    {uploading ? "Publishing Magazine..." : "Publish Event Magazine"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsUploadOpen(false)}
                    className="px-4 font-util text-eyebrow uppercase tracking-wider text-ink border border-line hover:bg-paper py-3 cursor-pointer"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
