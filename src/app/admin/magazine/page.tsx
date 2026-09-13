"use client";

import * as React from "react";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { User, MagazineIssue, Domain } from "@/lib/types";
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
  departmentId?: number | null;
  departmentName?: string | null;
  targetPageBudget?: number;
  orchestratorScore?: number;
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
  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [compilingId, setCompilingId] = useState<string | null>(null);

  // Modal State
  const [uploadMode, setUploadMode] = useState<"pdf" | "event">("event");
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  // Form Fields - Minimum Inputs for AI
  const [eventName, setEventName] = useState("");
  const [eventDate, setEventDate] = useState(new Date().toISOString().split("T")[0]);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState("");
  const [targetPageBudget, setTargetPageBudget] = useState(5);
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

  // Template Editor State
  const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false);
  const [templateName, setTemplateName] = useState("SIET Standard Issue Template");
  const [sectionSchema, setSectionSchema] = useState<any[]>([]);
  const [styleRules, setStyleRules] = useState<any>({
    accent_color: "#8B0000",
    background_color: "#FDFBF7",
    text_color: "#111111",
    font_display: "Playfair Display",
    font_body: "Source Serif Pro",
    spacing: "normal",
  });
  const [templateLoading, setTemplateLoading] = useState(false);
  const [templateSaving, setTemplateSaving] = useState(false);
  const [templateSuccess, setTemplateSuccess] = useState<string | null>(null);
  const [templateError, setTemplateError] = useState<string | null>(null);

  // End-to-End AI Pipeline State
  const [isEndToEndOpen, setIsEndToEndOpen] = useState(false);
  const [e2eFile, setE2eFile] = useState<File | null>(null);
  const [e2ePhotos, setE2ePhotos] = useState<File[]>([]);
  const [e2eTemplates, setE2eTemplates] = useState<File[]>([]);
  const [e2eDept, setE2eDept] = useState("AI Lab");
  const [e2eEventName, setE2eEventName] = useState("");
  const [e2eEventDate, setE2eEventDate] = useState(new Date().toISOString().split("T")[0]);
  const [e2eNotes, setE2eNotes] = useState("");
  const [e2eBudget, setE2eBudget] = useState(5);
  const [e2eRunning, setE2eRunning] = useState(false);
  const [e2eCurrentStage, setE2eCurrentStage] = useState<number>(0);
  const [e2eTelemetry, setE2eTelemetry] = useState<any[]>([]);
  const [e2eResult, setE2eResult] = useState<any | null>(null);
  const [e2eError, setE2eError] = useState<string | null>(null);

  const PIPELINE_STAGES = [
    { num: 1, name: "Reading documents", desc: "Parsing DOCX/PDF & template files" },
    { num: 2, name: "Extracting content", desc: "Chunking spans & metadata detection" },
    { num: 3, name: "Understanding sections", desc: "Qwen classifying sections & writing editorial copy" },
    { num: 4, name: "Selecting templates", desc: "Template intelligence matching lab/department" },
    { num: 5, name: "Matching photographs", desc: "SigLIP scoring real photographs" },
    { num: 6, name: "Planning pages", desc: "Multi-page planning & deterministic regions" },
    { num: 7, name: "Rendering pages", desc: "Template-driven PyMuPDF rendering" },
    { num: 8, name: "Validating pages", desc: "Visual QC checks & closed-loop recovery" },
    { num: 9, name: "Finalizing magazine", desc: "PDF compilation, previews & publishing" },
  ];

  const handleRunEndToEndPipeline = async () => {
    if (!e2eFile && !e2eNotes.trim() && !e2eEventName.trim()) {
      setE2eError("Please select a document file (.docx / .pdf), or provide event notes.");
      return;
    }
    setE2eRunning(true);
    setE2eError(null);
    setE2eResult(null);
    setE2eCurrentStage(1);

    const progressTimer = setInterval(() => {
      setE2eCurrentStage((prev) => (prev < 8 ? prev + 1 : prev));
    }, 1800);

    try {
      const formData = new FormData();
      if (e2eFile) formData.append("file", e2eFile);
      e2ePhotos.forEach((p) => formData.append("photos", p));
      e2eTemplates.forEach((t) => formData.append("templates", t));
      if (e2eEventName.trim()) formData.append("event_name", e2eEventName.trim());
      if (e2eEventDate) formData.append("event_date", e2eEventDate);
      formData.append("department_or_lab", e2eDept);
      if (e2eNotes.trim()) formData.append("raw_notes", e2eNotes.trim());
      formData.append("target_page_budget", String(e2eBudget));
      formData.append("publish_immediately", "true");
      formData.append("use_llm", "true");

      const res = await api.adminGenerateEndToEndMagazine(formData);
      clearInterval(progressTimer);
      setE2eCurrentStage(9);
      setE2eTelemetry(res.stage_telemetry || []);
      setE2eResult(res);
      await loadIssues();
    } catch (err: any) {
      clearInterval(progressTimer);
      setE2eError(err?.message || "Pipeline execution encountered an error.");
    } finally {
      setE2eRunning(false);
    }
  };

  const loadTemplate = async () => {
    setTemplateLoading(true);
    setTemplateError(null);
    try {
      const res = await api.adminGetTemplate();
      const data = res.data || res;
      setTemplateName(data.name || "SIET Standard Issue Template");
      setSectionSchema(Array.isArray(data.section_schema) ? data.section_schema : []);
      setStyleRules(data.style_rules || {
        accent_color: "#8B0000",
        background_color: "#FDFBF7",
        text_color: "#111111",
        font_display: "Playfair Display",
        font_body: "Source Serif Pro",
        spacing: "normal",
      });
    } catch (err: any) {
      console.error("Failed to load template:", err);
      setTemplateError("Failed to load active template.");
    } finally {
      setTemplateLoading(false);
    }
  };

  const handleOpenTemplateModal = () => {
    loadTemplate();
    setTemplateSuccess(null);
    setTemplateError(null);
    setIsTemplateModalOpen(true);
  };

  const handleSaveTemplate = async () => {
    setTemplateSaving(true);
    setTemplateError(null);
    setTemplateSuccess(null);
    try {
      const res = await api.adminUpdateTemplate({
        name: templateName,
        section_schema: sectionSchema,
        style_rules: styleRules,
      });
      const data = res.data || res;
      setTemplateName(data.name);
      setSectionSchema(data.section_schema);
      setStyleRules(data.style_rules);
      setTemplateSuccess("✅ Active template saved! Changes auto-apply to all future magazine generations.");
    } catch (err: any) {
      console.error("Save template error:", err);
      setTemplateError(err?.message || "Failed to save template changes.");
    } finally {
      setTemplateSaving(false);
    }
  };

  const handleUploadTemplateFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setTemplateSaving(true);
    setTemplateError(null);
    setTemplateSuccess(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await api.adminUploadTemplate(fd);
      const data = res.data || res;
      setTemplateName(data.name);
      setSectionSchema(data.section_schema);
      setStyleRules(data.style_rules);
      setTemplateSuccess("✨ Template uploaded & parsed! Headings mapped to section schema.");
    } catch (err: any) {
      console.error("Upload template error:", err);
      setTemplateError(err?.message || "Failed to parse template file.");
    } finally {
      setTemplateSaving(false);
    }
  };

  const moveSection = (idx: number, direction: "up" | "down") => {
    const newSchema = [...sectionSchema];
    const targetIdx = direction === "up" ? idx - 1 : idx + 1;
    if (targetIdx < 0 || targetIdx >= newSchema.length) return;
    const temp = newSchema[idx];
    newSchema[idx] = newSchema[targetIdx];
    newSchema[targetIdx] = temp;
    setSectionSchema(newSchema);
  };

  const toggleSectionEnabled = (idx: number) => {
    const newSchema = [...sectionSchema];
    newSchema[idx] = { ...newSchema[idx], enabled: !newSchema[idx].enabled };
    setSectionSchema(newSchema);
  };

  const updateSectionLabel = (idx: number, label: string) => {
    const newSchema = [...sectionSchema];
    newSchema[idx] = { ...newSchema[idx], label };
    setSectionSchema(newSchema);
  };

  const addCustomSection = () => {
    setSectionSchema((prev) => [
      ...prev,
      {
        section_type: `custom_${Date.now().toString().slice(-4)}`,
        label: "New Custom Section",
        enabled: true,
        layout_rules: { columns: 1 },
      },
    ]);
  };

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

    api.domains().then((res: any) => {
      const list = Array.isArray(res) ? res : (res?.data || []);
      setDomains(list);
    }).catch(() => {});

    const interval = setInterval(() => {
      api.adminListMagazines().then((data) => {
        if (Array.isArray(data)) setIssues(data as any);
      }).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleCompileMagazine = async (id: string) => {
    setCompilingId(id);
    try {
      await api.adminCompileMagazine(id);
      await loadIssues();
    } catch (err: any) {
      console.error("Compile error:", err);
      alert(err?.message || "Failed to compile magazine.");
    } finally {
      setCompilingId(null);
    }
  };

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
    setSelectedDepartmentId("");
    setTargetPageBudget(5);
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
        createFd.append("target_page_budget", String(targetPageBudget));

        if (selectedDepartmentId) {
          createFd.append("department_id", selectedDepartmentId);
          const matched = domains.find((d) => String(d.id || d.slug) === selectedDepartmentId || d.slug === selectedDepartmentId);
          if (matched) {
            createFd.append("department_name", matched.name);
          }
        }

        if (section2Mode === "ai_article" && aiGeneratedArticle) {
          createFd.append("writeup_headline", aiGeneratedArticle.headline);
          createFd.append("writeup_html", aiGeneratedArticle.html);
          createFd.append("writeup_text", rawNotes.trim() || aiGeneratedArticle.headline);
        }

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
            onClick={() => {
              setIsEndToEndOpen(true);
              setE2eError(null);
              setE2eResult(null);
            }}
            className="font-util text-eyebrow uppercase tracking-wider text-paper bg-emerald-700 hover:bg-emerald-800 border border-emerald-800 transition-colors px-4 py-2 cursor-pointer font-bold flex items-center gap-1.5 shadow-sm"
          >
            <span>🚀</span> End-to-End AI Pipeline
          </button>
          <button
            onClick={handleOpenTemplateModal}
            className="font-util text-eyebrow uppercase tracking-wider text-ink bg-paper-2 hover:bg-paper-3 border border-line transition-colors px-4 py-2 cursor-pointer font-bold flex items-center gap-1.5"
          >
            <span>🎨</span> Edit Active Template
          </button>
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
                    <div className="flex flex-wrap items-center gap-1.5 mb-0.5">
                      {issue.eventName && (
                        <span className="font-util text-[9px] uppercase tracking-wider text-accent font-bold">
                          📍 {issue.eventName}
                        </span>
                      )}
                      {issue.departmentName && (
                        <span className="font-util text-[9px] uppercase tracking-wider text-ink-soft bg-paper-3 px-1.5 py-0.5 border border-line">
                          🏛️ {issue.departmentName}
                        </span>
                      )}
                    </div>
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
                      onClick={() => handleCompileMagazine(issue.id)}
                      disabled={compilingId === issue.id}
                      className="font-util text-[10px] uppercase tracking-wider px-2 py-1 border border-ink/30 text-ink hover:bg-ink/5 cursor-pointer disabled:opacity-50"
                      title="Render high-resolution multi-page PDF immediately"
                    >
                      {compilingId === issue.id ? "Rendering..." : "⚡ Render PDF"}
                    </button>

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

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                        Department / Research Lab
                      </label>
                      <select
                        value={selectedDepartmentId}
                        onChange={(e) => setSelectedDepartmentId(e.target.value)}
                        className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink font-sans text-xs"
                      >
                        <option value="">General Engineering & Campus-Wide</option>
                        {domains.map((d) => (
                          <option key={d.id || d.slug} value={String(d.id || d.slug)}>
                            {d.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-1">
                      <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                        Target Page Budget
                      </label>
                      <select
                        value={targetPageBudget}
                        onChange={(e) => setTargetPageBudget(Number(e.target.value))}
                        className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink font-util text-xs"
                      >
                        <option value={4}>4 Pages (Standard Issue)</option>
                        <option value={5}>5 Pages (Editorial Digest + AI Digest)</option>
                        <option value={8}>8 Pages (Special Feature Edition)</option>
                        <option value={12}>12 Pages (Annual Symposium Volume)</option>
                      </select>
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

      {/* STRUCTURED TEMPLATE EDITOR MODAL */}
      {isTemplateModalOpen && (
        <div className="fixed inset-0 z-50 bg-paper/70 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
          <div className="w-full max-w-4xl border border-line bg-paper-2 p-6 space-y-6 shadow-xl my-8">
            {/* Header */}
            <div className="flex justify-between items-center border-b border-line pb-3">
              <div>
                <p className="font-util text-[9px] uppercase tracking-wider text-accent font-bold flex items-center gap-1">
                  <span>🎨</span> Admin Layout Engine
                </p>
                <h2 className="font-display text-body font-semibold text-ink">
                  Magazine Template &amp; Section Layout Editor
                </h2>
              </div>
              <button
                onClick={() => setIsTemplateModalOpen(false)}
                className="font-util text-eyebrow text-ink-soft hover:text-ink uppercase tracking-wider text-xs cursor-pointer"
              >
                [×]
              </button>
            </div>

            {templateLoading ? (
              <div className="p-8 text-center font-display text-xs italic text-ink-soft">
                Loading active template configuration...
              </div>
            ) : (
              <div className="space-y-6 text-xs">
                {/* Template Name & File Upload Bar */}
                <div className="bg-paper p-4 border border-line space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="space-y-1 flex-1">
                      <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider font-bold">
                        Template Name
                      </label>
                      <input
                        type="text"
                        value={templateName}
                        onChange={(e) => setTemplateName(e.target.value)}
                        className="w-full border border-line bg-paper-2 px-3 py-1.5 outline-none focus:border-ink font-medium"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider font-bold">
                        Upload Template File (.docx / .pdf)
                      </label>
                      <label className="font-util text-[10px] uppercase tracking-wider text-ink border border-line bg-paper-2 hover:bg-paper-3 px-3 py-1.5 cursor-pointer block text-center font-bold">
                        <span>📁 Select File</span>
                        <input
                          type="file"
                          accept=".docx,.doc,.pdf,.txt"
                          onChange={handleUploadTemplateFile}
                          className="hidden"
                        />
                      </label>
                    </div>
                  </div>
                </div>

                {/* Section Schema List (Drag / Reorder / Rename / Toggle) */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between border-b border-line pb-2">
                    <h3 className="font-util text-eyebrow text-ink uppercase tracking-wider font-bold flex items-center gap-1.5">
                      <span>📑</span> Section Layout &amp; Reordering
                    </h3>
                    <button
                      type="button"
                      onClick={addCustomSection}
                      className="font-util text-[10px] uppercase tracking-wider text-accent hover:underline cursor-pointer font-bold"
                    >
                      + Add Custom Section
                    </button>
                  </div>

                  <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                    {sectionSchema.map((sec, idx) => (
                      <div
                        key={idx}
                        className={`border p-3 flex flex-wrap sm:flex-nowrap items-center justify-between gap-3 transition-colors ${
                          sec.enabled ? "bg-paper border-line" : "bg-paper-3 border-line/60 opacity-60"
                        }`}
                      >
                        {/* Move Up/Down Controls */}
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            disabled={idx === 0}
                            onClick={() => moveSection(idx, "up")}
                            className="w-6 h-6 border border-line bg-paper-2 hover:bg-paper-3 text-ink flex items-center justify-center font-bold disabled:opacity-30 cursor-pointer"
                            title="Move Up"
                          >
                            ↑
                          </button>
                          <button
                            type="button"
                            disabled={idx === sectionSchema.length - 1}
                            onClick={() => moveSection(idx, "down")}
                            className="w-6 h-6 border border-line bg-paper-2 hover:bg-paper-3 text-ink flex items-center justify-center font-bold disabled:opacity-30 cursor-pointer"
                            title="Move Down"
                          >
                            ↓
                          </button>
                          <span className="font-util text-[10px] text-ink-soft w-5 text-center font-bold">
                            #{idx + 1}
                          </span>
                        </div>

                        {/* Section Label & Type */}
                        <div className="flex-1 flex items-center gap-2">
                          <input
                            type="text"
                            value={sec.label || ""}
                            onChange={(e) => updateSectionLabel(idx, e.target.value)}
                            className="w-full border border-line bg-paper-2 px-3 py-1 text-xs outline-none focus:border-ink font-medium"
                          />
                          <span className="font-util text-[9px] uppercase tracking-wider text-accent bg-accent/10 border border-accent/20 px-2 py-0.5 whitespace-nowrap font-bold">
                            {sec.section_type}
                          </span>
                        </div>

                        {/* Toggle On/Off */}
                        <label className="flex items-center gap-2 cursor-pointer font-util text-[10px] uppercase tracking-wider font-semibold">
                          <input
                            type="checkbox"
                            checked={Boolean(sec.enabled)}
                            onChange={() => toggleSectionEnabled(idx)}
                            className="accent-accent cursor-pointer"
                          />
                          <span>{sec.enabled ? "Active" : "Disabled"}</span>
                        </label>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Style Rules Form */}
                <div className="space-y-3 border-t border-line pt-4">
                  <h3 className="font-util text-eyebrow text-ink uppercase tracking-wider font-bold flex items-center gap-1.5">
                    <span>🎨</span> House Styling &amp; Typography Rules
                  </h3>

                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 bg-paper p-4 border border-line">
                    <div className="space-y-1">
                      <label className="block font-util text-[10px] text-ink-soft uppercase tracking-wider font-semibold">
                        Accent Color
                      </label>
                      <div className="flex items-center gap-2">
                        <input
                          type="color"
                          value={styleRules.accent_color || "#8B0000"}
                          onChange={(e) => setStyleRules({ ...styleRules, accent_color: e.target.value })}
                          className="w-8 h-8 cursor-pointer border border-line bg-paper p-0.5"
                        />
                        <input
                          type="text"
                          value={styleRules.accent_color || "#8B0000"}
                          onChange={(e) => setStyleRules({ ...styleRules, accent_color: e.target.value })}
                          className="w-full border border-line bg-paper-2 px-2 py-1 font-mono text-xs"
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <label className="block font-util text-[10px] text-ink-soft uppercase tracking-wider font-semibold">
                        Headline Font
                      </label>
                      <select
                        value={styleRules.font_display || "Playfair Display"}
                        onChange={(e) => setStyleRules({ ...styleRules, font_display: e.target.value })}
                        className="w-full border border-line bg-paper-2 px-2 py-1.5 text-xs outline-none cursor-pointer"
                      >
                        <option value="Playfair Display">Playfair Display (Editorial Serif)</option>
                        <option value="Cinzel">Cinzel (Classic Serif)</option>
                        <option value="Lora">Lora (Modern Serif)</option>
                        <option value="Inter">Inter (Clean Sans)</option>
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="block font-util text-[10px] text-ink-soft uppercase tracking-wider font-semibold">
                        Body Font
                      </label>
                      <select
                        value={styleRules.font_body || "Source Serif Pro"}
                        onChange={(e) => setStyleRules({ ...styleRules, font_body: e.target.value })}
                        className="w-full border border-line bg-paper-2 px-2 py-1.5 text-xs outline-none cursor-pointer"
                      >
                        <option value="Source Serif Pro">Source Serif Pro (Book)</option>
                        <option value="Georgia">Georgia (Traditional)</option>
                        <option value="Inter">Inter (Modern Sans)</option>
                        <option value="Roboto">Roboto (Technical Sans)</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Status Messages */}
                {templateSuccess && (
                  <div className="p-3 bg-emerald-50 border border-emerald-300 text-emerald-800 font-util text-[10px] uppercase tracking-wider font-bold">
                    {templateSuccess}
                  </div>
                )}
                {templateError && (
                  <div className="p-3 bg-rose-50 border border-rose-300 text-rose-800 font-util text-[10px] uppercase tracking-wider font-bold">
                    {templateError}
                  </div>
                )}

                {/* Footer Save Button */}
                <div className="flex justify-end gap-3 border-t border-line pt-4">
                  <button
                    type="button"
                    onClick={() => setIsTemplateModalOpen(false)}
                    className="font-util text-eyebrow uppercase tracking-wider text-ink border border-line px-4 py-2 hover:bg-paper-3 cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveTemplate}
                    disabled={templateSaving}
                    className="font-util text-eyebrow uppercase tracking-wider text-paper bg-ink hover:bg-accent border border-ink px-6 py-2 transition-colors cursor-pointer font-bold disabled:opacity-50"
                  >
                    {templateSaving ? "Saving Template..." : "Save Active Template"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* END-TO-END AI MAGAZINE GENERATION PIPELINE MODAL */}
      {isEndToEndOpen && (
        <div className="fixed inset-0 z-50 bg-paper/80 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
          <div className="w-full max-w-4xl border border-line bg-paper-2 p-6 space-y-6 shadow-2xl my-8 max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex justify-between items-start border-b border-line pb-4">
              <div>
                <p className="font-util text-[10px] uppercase tracking-wider text-emerald-700 font-bold flex items-center gap-1.5">
                  <span>🚀</span> End-to-End Autonomous Publication
                </p>
                <h2 className="font-display text-h3 font-semibold text-ink mt-0.5">
                  AI Magazine Generation Pipeline
                </h2>
                <p className="font-body text-xs text-ink-soft">
                  Integrates Document Parsing, Qwen RAG Understanding, Template Intelligence, SigLIP Real-Photo Matching, Multi-Page Layout Planning, Template-Driven Rendering, and 10-Check Visual Quality Control.
                </p>
              </div>
              <button
                onClick={() => {
                  if (!e2eRunning) setIsEndToEndOpen(false);
                }}
                disabled={e2eRunning}
                className="font-util text-eyebrow text-ink-soft hover:text-ink uppercase tracking-wider text-xs cursor-pointer disabled:opacity-30"
              >
                [×] Close
              </button>
            </div>

            {/* Pipeline Configuration Form */}
            {!e2eRunning && !e2eResult && (
              <div className="space-y-4 text-xs">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Source Document File */}
                  <div className="bg-paper p-3.5 border border-line space-y-2 rounded-xs">
                    <label className="block font-util text-eyebrow text-ink uppercase tracking-wider font-bold">
                      1. Event Report Document (.docx / .pdf / .txt)
                    </label>
                    <input
                      type="file"
                      accept=".docx,.doc,.pdf,.txt,.md"
                      onChange={(e) => setE2eFile(e.target.files?.[0] || null)}
                      className="w-full text-xs font-util file:mr-2 file:py-1.5 file:px-3 file:border-0 file:text-[10px] file:uppercase file:tracking-wider file:font-semibold file:bg-paper-3 file:text-ink hover:file:bg-line cursor-pointer"
                    />
                    {e2eFile && (
                      <p className="font-util text-[10px] text-emerald-700 font-medium">
                        ✓ Selected: {e2eFile.name} ({(e2eFile.size / 1024).toFixed(1)} KB)
                      </p>
                    )}
                  </div>

                  {/* Real Photographs */}
                  <div className="bg-paper p-3.5 border border-line space-y-2 rounded-xs">
                    <label className="block font-util text-eyebrow text-ink uppercase tracking-wider font-bold">
                      2. Real College Photographs (SigLIP Ranked)
                    </label>
                    <input
                      type="file"
                      multiple
                      accept="image/*"
                      onChange={(e) => setE2ePhotos(Array.from(e.target.files || []))}
                      className="w-full text-xs font-util file:mr-2 file:py-1.5 file:px-3 file:border-0 file:text-[10px] file:uppercase file:tracking-wider file:font-semibold file:bg-paper-3 file:text-ink hover:file:bg-line cursor-pointer"
                    />
                    <p className="font-util text-[10px] text-ink-soft">
                      {e2ePhotos.length > 0
                        ? `✓ ${e2ePhotos.length} real photos uploaded`
                        : "Strictly real photographs preferred. Zero synthetic AI generation."}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {/* Department / Lab Selector */}
                  <div className="space-y-1">
                    <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider font-semibold">
                      Department / Lab Template Group
                    </label>
                    <select
                      value={e2eDept}
                      onChange={(e) => setE2eDept(e.target.value)}
                      className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink font-medium"
                    >
                      <option value="AI Lab">AI Lab (Neural / High-Tech)</option>
                      <option value="IoT Lab">IoT Lab (Embedded / Hardware)</option>
                      <option value="Robotics Lab">Robotics Lab (Automation / Systems)</option>
                      <option value="Cyber Security Lab">Cyber Security Lab (Security / Defense)</option>
                      <option value="Research Lab">Research Lab (Academic Spread)</option>
                      <option value="Department activities">Department Activities</option>
                      <option value="Student achievements">Student Achievements</option>
                      <option value="Faculty achievements">Faculty Achievements</option>
                      <option value="Events">Events &amp; Symposia</option>
                      <option value="Projects">Projects &amp; Prototypes</option>
                    </select>
                  </div>

                  {/* Event Name */}
                  <div className="space-y-1">
                    <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider font-semibold">
                      Event / Topic (Optional)
                    </label>
                    <input
                      type="text"
                      value={e2eEventName}
                      onChange={(e) => setE2eEventName(e.target.value)}
                      placeholder="Auto-detected from file if blank"
                      className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink"
                    />
                  </div>

                  {/* Target Page Budget */}
                  <div className="space-y-1">
                    <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider font-semibold">
                      Target Page Budget ({e2eBudget} Pages)
                    </label>
                    <input
                      type="range"
                      min={2}
                      max={10}
                      value={e2eBudget}
                      onChange={(e) => setE2eBudget(Number(e.target.value))}
                      className="w-full accent-emerald-700 cursor-pointer mt-2"
                    />
                  </div>
                </div>

                {/* Raw Notes Fallback */}
                <div className="space-y-1">
                  <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider font-semibold">
                    Raw Event Notes / Supplementary Text (Optional)
                  </label>
                  <textarea
                    rows={3}
                    value={e2eNotes}
                    onChange={(e) => setE2eNotes(e.target.value)}
                    placeholder="Provide additional details, student names, project highlights, or agenda notes..."
                    className="w-full border border-line bg-paper p-2.5 outline-none focus:border-ink"
                  />
                </div>

                {e2eError && (
                  <div className="p-3 bg-rose-50 border border-rose-300 text-rose-800 font-util text-[10px] uppercase tracking-wider font-bold">
                    ⚠️ {e2eError}
                  </div>
                )}

                {/* Run Button */}
                <div className="pt-2 flex justify-end">
                  <button
                    type="button"
                    onClick={handleRunEndToEndPipeline}
                    className="font-util text-eyebrow uppercase tracking-wider text-paper bg-emerald-700 hover:bg-emerald-800 border border-emerald-800 px-6 py-3 cursor-pointer font-bold shadow-md flex items-center gap-2"
                  >
                    <span>⚡</span> Run 9-Stage AI Generation Pipeline
                  </button>
                </div>
              </div>
            )}

            {/* Active 9-Stage Progress Tracker */}
            {(e2eRunning || (e2eResult && e2eTelemetry.length > 0)) && (
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-line pb-2">
                  <span className="font-util text-[10px] uppercase tracking-wider text-emerald-800 font-bold flex items-center gap-1.5">
                    {e2eRunning ? (
                      <>
                        <span className="animate-spin text-sm">⚙️</span> Generation In Progress (Stage {e2eCurrentStage} of 9)...
                      </>
                    ) : (
                      <>
                        <span>✅</span> Generation Complete
                      </>
                    )}
                  </span>
                  <span className="font-util text-[10px] text-ink-soft">
                    {e2eResult ? `${e2eResult.total_pages} Pages · QC Score: ${e2eResult.overall_quality_score}/100` : "Autonomous Flow"}
                  </span>
                </div>

                {/* 9-Stage Stepper Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                  {PIPELINE_STAGES.map((st) => {
                    const isPassed = e2eResult || st.num < e2eCurrentStage;
                    const isActive = e2eRunning && st.num === e2eCurrentStage;
                    const tele = e2eTelemetry.find((t: any) => t.stage_number === st.num);

                    return (
                      <div
                        key={st.num}
                        className={`p-3 border rounded-xs transition-all ${
                          isActive
                            ? "border-emerald-600 bg-emerald-50/70 shadow-sm ring-1 ring-emerald-600"
                            : isPassed
                            ? "border-emerald-200 bg-emerald-50/30 text-ink"
                            : "border-line bg-paper/60 text-ink-soft opacity-60"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-util text-[9px] uppercase tracking-wider font-bold">
                            Stage {st.num}
                          </span>
                          <span className="text-xs">
                            {isPassed ? "✓" : isActive ? "⏳" : "○"}
                          </span>
                        </div>
                        <p className="font-display text-xs font-semibold text-ink mt-0.5">
                          {st.num}. {st.name}
                        </p>
                        <p className="font-body text-[10px] text-ink-soft mt-0.5 line-clamp-1">
                          {tele?.message || st.desc}
                        </p>
                        {tele && tele.elapsed_seconds > 0 && (
                          <p className="font-util text-[9px] text-emerald-700 font-mono mt-1">
                            ⏱ {tele.elapsed_seconds}s
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Completion Result Card & Previews */}
            {e2eResult && (
              <div className="bg-paper p-5 border border-emerald-300 rounded-xs space-y-4 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-line pb-3">
                  <div>
                    <span className="font-util text-[9px] uppercase tracking-wider text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 border border-emerald-200">
                      Publication Ready · Score: {e2eResult.overall_quality_score}/100
                    </span>
                    <h3 className="font-display text-base font-semibold text-ink mt-1">
                      {e2eResult.title}
                    </h3>
                    <p className="font-body text-xs text-ink-soft">
                      {e2eResult.department_or_lab} · {e2eResult.total_pages} Pages Rendered in {e2eResult.execution_time_seconds}s
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {e2eResult.pdf_url && (
                      <a
                        href={e2eResult.pdf_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-util text-eyebrow uppercase tracking-wider text-paper bg-emerald-700 hover:bg-emerald-800 px-4 py-2 font-bold flex items-center gap-1.5"
                      >
                        <span>📥</span> Download PDF
                      </a>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        setIsEndToEndOpen(false);
                        setE2eResult(null);
                      }}
                      className="font-util text-eyebrow uppercase tracking-wider text-ink border border-line px-4 py-2 hover:bg-paper-3 cursor-pointer"
                    >
                      Done
                    </button>
                  </div>
                </div>

                {/* Rendered Page Thumbnails */}
                {e2eResult.page_previews && e2eResult.page_previews.length > 0 && (
                  <div className="space-y-2">
                    <p className="font-util text-[10px] uppercase tracking-wider text-ink-soft font-semibold">
                      Rendered Publication Pages ({e2eResult.page_previews.length}):
                    </p>
                    <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-3">
                      {e2eResult.page_previews.map((previewUrl: string, idx: number) => (
                        <div key={idx} className="border border-line bg-paper-3 p-1 rounded-xs space-y-1">
                          <img
                            src={previewUrl}
                            alt={`Page ${idx + 1}`}
                            className="w-full h-32 object-cover border border-line shadow-2xs"
                          />
                          <p className="font-util text-[9px] text-center text-ink-soft uppercase font-bold">
                            Page {idx + 1}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
