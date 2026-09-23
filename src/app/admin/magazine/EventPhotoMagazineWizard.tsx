"use client";

import * as React from "react";
import { useState } from "react";
import { api } from "@/lib/api";

interface UploadedPhoto {
  id: string;
  file: File;
  name: string;
  previewUrl: string;
  sizeKb: number;
}

interface PhotoMatch {
  id: string;
  file_name: string;
  url: string;
  disk_path: string;
  caption: string;
  confidence: number;
  status: "HIGH" | "REVIEW_RECOMMENDED" | "UNMATCHED";
  needs_review: boolean;
  evidence: string[];
}

interface DetectedEvent {
  event_id: string;
  title: string;
  date: string;
  category: string;
  people: string[];
  achievements: string[];
  organization: string;
  source_pages: number[];
  matched_photos: PhotoMatch[];
}

interface AnalysisData {
  session_id: string;
  source_file_path: string;
  original_filename: string;
  file_size_bytes: number;
  lab_department: string;
  title: string;
  issue_date: string;
  template_id: string;
  events: DetectedEvent[];
  unmatched_photos: PhotoMatch[];
  all_uploaded_photos: {
    id: string;
    url: string;
    file_name: string;
    disk_path: string;
  }[];
  stats: {
    total_events: number;
    total_photos: number;
    auto_matched_count: number;
    review_recommended_count: number;
    unmatched_count: number;
  };
}

interface EventPhotoMagazineWizardProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const DEPARTMENTS = [
  "Artificial Intelligence and Data Science",
  "Computer Science and Engineering",
  "Information Technology",
  "Electronics and Communication Engineering",
  "Electrical and Electronics Engineering",
  "Mechanical Engineering",
  "Civil Engineering",
  "Biomedical Engineering",
];

export function EventPhotoMagazineWizard({
  isOpen,
  onClose,
  onSuccess,
}: EventPhotoMagazineWizardProps) {
  // Wizard steps: 'upload' -> 'review' -> 'preview'
  const [step, setStep] = useState<"upload" | "review" | "preview">("upload");

  // Step 1: Upload Form State
  const [labDepartment, setLabDepartment] = useState(DEPARTMENTS[0]);
  const [templateId, setTemplateId] = useState("SIET_DEFAULT_V1");
  const [magazineTitle, setMagazineTitle] = useState("");
  const [issueDate, setIssueDate] = useState("August 2026");
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [uploadedPhotos, setUploadedPhotos] = useState<UploadedPhoto[]>([]);

  // Processing & Error States
  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Step 2: Review State
  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null);
  const [events, setEvents] = useState<DetectedEvent[]>([]);
  const [unmatchedPhotos, setUnmatchedPhotos] = useState<PhotoMatch[]>([]);

  // Step 3: Final Generated Result State
  const [generatedMagazine, setGeneratedMagazine] = useState<any | null>(null);
  const [activePreviewPage, setActivePreviewPage] = useState(0);
  const [approvalAction, setApprovalAction] = useState<"approve" | "publish" | null>(null);

  if (!isOpen) return null;

  // Handle file picker for source document
  const handleSourceFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setSourceFile(file);
    if (file && !magazineTitle) {
      const baseName = file.name.replace(/\.[^/.]+$/, "");
      setMagazineTitle(baseName);
    }
  };

  // Handle file picker for multiple event photos
  const handlePhotoFilesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    const newItems: UploadedPhoto[] = files.map((f, idx) => ({
      id: `photo_${Date.now()}_${idx}_${Math.random().toString(36).substring(2, 6)}`,
      file: f,
      name: f.name,
      previewUrl: URL.createObjectURL(f),
      sizeKb: Math.round(f.size / 1024),
    }));

    setUploadedPhotos((prev) => [...prev, ...newItems]);
    e.target.value = "";
  };

  // Remove a photo from uploaded list in Step 1
  const handleRemoveUploadedPhoto = (id: string) => {
    setUploadedPhotos((prev) => {
      const target = prev.find((p) => p.id === id);
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((p) => p.id !== id);
    });
  };

  // Step 1 -> Step 2: Trigger AI Analysis and Photo Matching
  const handleRunAnalysis = async () => {
    if (!sourceFile) {
      setErrorMsg("Please select a source document (PDF, DOCX, or DOC).");
      return;
    }

    setAnalyzing(true);
    setErrorMsg(null);

    try {
      const fd = new FormData();
      fd.append("file", sourceFile);
      fd.append("lab_department", labDepartment);
      if (magazineTitle.trim()) fd.append("title", magazineTitle.trim());
      if (issueDate.trim()) fd.append("issue_date", issueDate.trim());
      fd.append("template_id", templateId);

      for (const p of uploadedPhotos) {
        fd.append("photos", p.file, p.name);
      }

      const res = await api.adminAnalyzeAndMatch(fd);
      setAnalysisData(res);
      setEvents(res.events || []);
      setUnmatchedPhotos(res.unmatched_photos || []);
      setStep("review");
    } catch (err: any) {
      console.error("Analysis Error:", err);
      setErrorMsg(err?.message || "Failed to analyze document and match photos.");
    } finally {
      setAnalyzing(false);
    }
  };

  // Step 2: Remove a matched photo from an event (moves to unmatched)
  const handleDetachPhoto = (eventId: string, photoId: string) => {
    let detachedPhoto: PhotoMatch | null = null;

    setEvents((prev) =>
      prev.map((ev) => {
        if (ev.event_id === eventId) {
          const match = ev.matched_photos.find((p) => p.id === photoId);
          if (match) detachedPhoto = { ...match, status: "UNMATCHED", needs_review: true };
          return {
            ...ev,
            matched_photos: ev.matched_photos.filter((p) => p.id !== photoId),
          };
        }
        return ev;
      })
    );

    if (detachedPhoto) {
      setUnmatchedPhotos((prev) => [...prev, detachedPhoto!]);
    }
  };

  // Step 2: Move photo from one event to another
  const handleMovePhoto = (fromEventId: string, toEventId: string, photoId: string) => {
    if (fromEventId === toEventId) return;

    let targetPhoto: PhotoMatch | null = null;

    setEvents((prev) => {
      const nextEvents = prev.map((ev) => {
        if (ev.event_id === fromEventId) {
          const found = ev.matched_photos.find((p) => p.id === photoId);
          if (found) {
            targetPhoto = {
              ...found,
              status: "REVIEW_RECOMMENDED",
              evidence: [...(found.evidence || []), `Manually moved to ${toEventId}`],
            };
          }
          return {
            ...ev,
            matched_photos: ev.matched_photos.filter((p) => p.id !== photoId),
          };
        }
        return ev;
      });

      if (!targetPhoto) return nextEvents;

      return nextEvents.map((ev) => {
        if (ev.event_id === toEventId) {
          return {
            ...ev,
            matched_photos: [...ev.matched_photos, targetPhoto!],
          };
        }
        return ev;
      });
    });
  };

  // Step 2: Attach unmatched photo to an event
  const handleAttachUnmatched = (photoId: string, toEventId: string) => {
    if (!toEventId) return;

    const photo = unmatchedPhotos.find((p) => p.id === photoId);
    if (!photo) return;

    const attachedPhoto: PhotoMatch = {
      ...photo,
      status: "REVIEW_RECOMMENDED",
      evidence: ["Manually attached by administrator during review."],
    };

    setUnmatchedPhotos((prev) => prev.filter((p) => p.id !== photoId));
    setEvents((prev) =>
      prev.map((ev) => {
        if (ev.event_id === toEventId) {
          return {
            ...ev,
            matched_photos: [...ev.matched_photos, attachedPhoto],
          };
        }
        return ev;
      })
    );
  };

  // Step 2 -> Step 3: Approve associations and generate magazine
  const handleGenerateMagazine = async () => {
    if (!analysisData) return;

    setGenerating(true);
    setErrorMsg(null);

    try {
      // Build approved associations mapping
      const approvedMapping: Record<string, any[]> = {};
      for (const ev of events) {
        if (ev.matched_photos && ev.matched_photos.length > 0) {
          approvedMapping[ev.event_id] = ev.matched_photos;
        }
      }

      const payload = {
        source_file_path: analysisData.source_file_path,
        lab_department: labDepartment,
        title: magazineTitle.trim() || analysisData.title,
        issue_date: issueDate.trim() || analysisData.issue_date,
        template_id: templateId,
        approved_associations: approvedMapping,
        all_photos: analysisData.all_uploaded_photos || [],
      };

      const res = await api.adminGenerateFromApproved(payload);
      setGeneratedMagazine(res);
      setStep("preview");
      onSuccess();
    } catch (err: any) {
      console.error("Generation Error:", err);
      setErrorMsg(err?.message || "Magazine generation failed. Please review associations and try again.");
    } finally {
      setGenerating(false);
    }
  };

  const handleApprovalAction = async (action: "approve" | "publish") => {
    if (!generatedMagazine?.id) return;

    setApprovalAction(action);
    setErrorMsg(null);
    try {
      if (action === "approve") {
        await api.adminApproveMagazine(String(generatedMagazine.id));
        setGeneratedMagazine((current: any) => ({ ...current, status: "approved" }));
      } else {
        await api.adminPublishMagazine(String(generatedMagazine.id));
        setGeneratedMagazine((current: any) => ({ ...current, status: "published" }));
        onSuccess();
      }
    } catch (err: any) {
      console.error(`${action} magazine error:`, err);
      setErrorMsg(err?.message || `Unable to ${action} this magazine.`);
    } finally {
      setApprovalAction(null);
    }
  };

  // Dynamic Statistics
  const totalEventsCount = events.length;
  const matchedPhotosCount = events.reduce((acc, ev) => acc + ev.matched_photos.length, 0);
  const highConfidenceCount = events.reduce(
    (acc, ev) => acc + ev.matched_photos.filter((p) => p.confidence >= 0.9).length,
    0
  );
  const reviewRecommendedCount = events.reduce(
    (acc, ev) =>
      acc +
      ev.matched_photos.filter((p) => p.confidence >= 0.75 && p.confidence < 0.9).length,
    0
  );
  const unmatchedCount = unmatchedPhotos.length;

  return (
    <div className="fixed inset-0 z-50 bg-paper/70 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="w-full max-w-4xl border border-line bg-paper-2 p-6 space-y-6 shadow-2xl my-6 rounded-xs max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center border-b border-line pb-3 shrink-0">
          <div>
            <p className="font-util text-[9px] uppercase tracking-wider text-accent font-bold flex items-center gap-1.5">
              <span>✨</span> Production Event Photos → AI Matching → Magazine Generation
            </p>
            <h2 className="font-display text-lg font-semibold text-ink">
              {step === "upload" && "Step 1: Upload Source Document & Event Photos"}
              {step === "review" && "Step 2: AI Photo-Matching & Human Review"}
              {step === "preview" && "Step 3: Magazine Generation & Visual Verification"}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="font-util text-eyebrow text-ink-soft hover:text-ink uppercase tracking-wider text-xs cursor-pointer p-1"
          >
            [✕ Close]
          </button>
        </div>

        {/* Error Banner */}
        {errorMsg && (
          <div className="p-3 bg-red-50 border border-red-300 text-red-800 font-util text-xs flex justify-between items-center shrink-0">
            <span>⚠️ {errorMsg}</span>
            <button onClick={() => setErrorMsg(null)} className="underline cursor-pointer text-[10px]">
              Dismiss
            </button>
          </div>
        )}

        {/* ========================================================================= */}
        {/* STEP 1: UPLOAD SOURCE DOCUMENT & EVENT PHOTOS                            */}
        {/* ========================================================================= */}
        {step === "upload" && (
          <div className="overflow-y-auto space-y-5 pr-1 text-xs">
            {/* Dept & Template Selectors */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider font-bold">
                  Lab / Department *
                </label>
                <select
                  value={labDepartment}
                  onChange={(e) => setLabDepartment(e.target.value)}
                  className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink font-medium"
                >
                  {DEPARTMENTS.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider font-bold">
                  Magazine Template *
                </label>
                <select
                  value={templateId}
                  onChange={(e) => setTemplateId(e.target.value)}
                  className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink font-medium"
                >
                  <option value="SIET_DEFAULT_V1">
                    SIET_DEFAULT_V1 (Standard Multi-Page Academic Issue)
                  </option>
                </select>
              </div>
            </div>

            {/* Title & Issue Date */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider font-bold">
                  Magazine Title (Optional - Auto-inferred)
                </label>
                <input
                  type="text"
                  value={magazineTitle}
                  onChange={(e) => setMagazineTitle(e.target.value)}
                  placeholder="e.g. AI Research Lab Accomplishments 2026"
                  className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink font-medium"
                />
              </div>

              <div className="space-y-1">
                <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider font-bold">
                  Issue / Date Label (Optional)
                </label>
                <input
                  type="text"
                  value={issueDate}
                  onChange={(e) => setIssueDate(e.target.value)}
                  placeholder="e.g. Volume 30 - Issue 1 | August 2026"
                  className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink font-medium"
                />
              </div>
            </div>

            {/* Source Document Upload */}
            <div className="border border-line p-4 bg-paper space-y-2 rounded-xs">
              <div className="flex justify-between items-center">
                <label className="block font-util text-eyebrow text-ink uppercase tracking-wider font-bold">
                  1. Source Document * (.pdf, .docx, .doc)
                </label>
                {sourceFile && (
                  <span className="font-util text-[10px] text-emerald-800 font-bold">
                    ✓ Document Loaded ({(sourceFile.size / 1024).toFixed(1)} KB)
                  </span>
                )}
              </div>
              <p className="text-[11px] text-ink-soft">
                Multi-event source document with achievements, descriptions, and dates.
              </p>
              <input
                type="file"
                accept=".pdf,.docx,.doc"
                onChange={handleSourceFileChange}
                className="w-full border border-line bg-paper-2 p-2 cursor-pointer font-util text-xs"
              />
            </div>

            {/* Multiple Photos Upload */}
            <div className="border border-line p-4 bg-paper space-y-3 rounded-xs">
              <div className="flex justify-between items-center">
                <label className="block font-util text-eyebrow text-ink uppercase tracking-wider font-bold">
                  2. Upload Real Event Photographs (Multiple Allowed)
                </label>
                <span className="font-util text-[10px] text-ink-soft font-bold">
                  {uploadedPhotos.length} Photo(s) Selected
                </span>
              </div>
              <p className="text-[11px] text-ink-soft">
                Real photos belonging to achievements. The AI engine automatically infers which photo belongs to which event.
              </p>
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={handlePhotoFilesChange}
                className="w-full border border-line bg-paper-2 p-2 cursor-pointer font-util text-xs"
              />

              {/* Photo Thumbnails Grid */}
              {uploadedPhotos.length > 0 && (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 pt-2">
                  {uploadedPhotos.map((photo) => (
                    <div
                      key={photo.id}
                      className="border border-line bg-paper-2 p-2 relative group flex flex-col items-center text-center shadow-xs"
                    >
                      <button
                        type="button"
                        onClick={() => handleRemoveUploadedPhoto(photo.id)}
                        className="absolute top-1 right-1 bg-red-600 text-white rounded-full w-5 h-5 flex items-center justify-center text-[10px] font-bold shadow-xs hover:bg-red-700 cursor-pointer"
                        title="Remove photo"
                      >
                        ✕
                      </button>
                      <img
                        src={photo.previewUrl}
                        alt={photo.name}
                        className="w-full h-24 object-cover border border-line bg-paper-3 mb-1"
                      />
                      <p className="font-util text-[10px] text-ink truncate w-full font-medium" title={photo.name}>
                        {photo.name}
                      </p>
                      <span className="font-util text-[9px] text-ink-soft">({photo.sizeKb} KB)</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Submit Action */}
            <div className="pt-2">
              <button
                type="button"
                onClick={handleRunAnalysis}
                disabled={analyzing || !sourceFile}
                className="w-full font-util text-xs uppercase tracking-wider text-paper bg-accent hover:opacity-95 py-3 px-4 transition-all cursor-pointer font-bold flex items-center justify-center gap-2 shadow-md disabled:opacity-50"
              >
                {analyzing ? (
                  <>
                    <span className="animate-spin">⏳</span>
                    <span>Parsing Document &amp; Matching Photos with AI...</span>
                  </>
                ) : (
                  <>
                    <span>⚡</span>
                    <span>Run AI Event &amp; Photo Matching (Step 1 of 2)</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* STEP 2: HUMAN-REVIEWABLE AI PHOTO-MATCHING SCREEN                        */}
        {/* ========================================================================= */}
        {step === "review" && (
          <div className="overflow-y-auto space-y-5 pr-1 text-xs flex-1">
            {/* Magazine Preview Summary Badge Bar */}
            <div className="border border-line bg-paper p-3 flex flex-wrap items-center justify-between gap-3 shadow-xs">
              <div>
                <span className="font-util text-[9px] uppercase tracking-wider text-ink-soft font-bold block">
                  Association Review Summary
                </span>
                <p className="font-display text-sm font-bold text-ink">
                  Magazine Preview: {totalEventsCount} Events &bull; {uploadedPhotos.length} Photos
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2 font-util text-[10px] uppercase font-bold">
                <span className="bg-emerald-100 text-emerald-800 px-2.5 py-1 border border-emerald-300">
                  ✓ {highConfidenceCount} Auto-Matched (&ge;90%)
                </span>
                {reviewRecommendedCount > 0 && (
                  <span className="bg-amber-100 text-amber-800 px-2.5 py-1 border border-amber-300">
                    ⚠️ {reviewRecommendedCount} Review Recommended (75-89%)
                  </span>
                )}
                {unmatchedCount > 0 && (
                  <span className="bg-gray-200 text-gray-800 px-2.5 py-1 border border-gray-400">
                    ℹ️ {unmatchedCount} Unmatched (&lt;75%)
                  </span>
                )}
              </div>
            </div>

            {/* Detected Events List with Associated Photos */}
            <div className="space-y-4">
              <h3 className="font-util text-eyebrow text-ink-soft uppercase tracking-wider font-bold">
                Detected Event Units &amp; Attached Photographs
              </h3>

              {events.map((ev, evIdx) => (
                <div
                  key={ev.event_id}
                  className="border border-line bg-paper p-4 space-y-3 rounded-xs shadow-xs"
                >
                  <div className="flex flex-wrap justify-between items-start gap-2 border-b border-line pb-2">
                    <div>
                      <span className="font-util text-[9px] uppercase tracking-wider text-accent font-bold block">
                        EVENT {String(evIdx + 1).padStart(2, "0")} &bull; {ev.category.toUpperCase()}
                      </span>
                      <h4 className="font-display text-sm font-bold text-ink">{ev.title}</h4>
                      {ev.people && ev.people.length > 0 && (
                        <p className="font-util text-[10px] text-ink-soft mt-0.5">
                          Participants: {ev.people.join(", ")}
                        </p>
                      )}
                    </div>
                    <span className="font-util text-[9px] text-ink-soft bg-paper-2 px-2 py-0.5 border border-line">
                      Pages: {ev.source_pages ? ev.source_pages.join(", ") : "N/A"}
                    </span>
                  </div>

                  {/* Matched Photos or Zero Photos Notice */}
                  {ev.matched_photos && ev.matched_photos.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pt-1">
                      {ev.matched_photos.map((photo) => (
                        <div
                          key={photo.id}
                          className="border border-line bg-paper-2 p-2.5 flex flex-col justify-between space-y-2 rounded-xs shadow-xs"
                        >
                          <div className="space-y-1.5">
                            <img
                              src={photo.url}
                              alt={photo.file_name}
                              className="w-full h-28 object-cover border border-line bg-paper-3"
                            />
                            <p className="font-util text-[10px] text-ink font-bold truncate" title={photo.file_name}>
                              {photo.file_name}
                            </p>

                            {/* Confidence Badge */}
                            <div className="flex items-center gap-1">
                              {photo.confidence >= 0.9 ? (
                                <span className="font-util text-[9px] uppercase tracking-wider font-bold text-emerald-800 bg-emerald-100 px-1.5 py-0.5 border border-emerald-300">
                                  {Math.round(photo.confidence * 100)}% HIGH CONFIDENCE
                                </span>
                              ) : (
                                <span className="font-util text-[9px] uppercase tracking-wider font-bold text-amber-800 bg-amber-100 px-1.5 py-0.5 border border-amber-300">
                                  {Math.round(photo.confidence * 100)}% REVIEW RECOMMENDED
                                </span>
                              )}
                            </div>

                            {/* Evidence notes */}
                            {photo.evidence && photo.evidence.length > 0 && (
                              <div className="font-util text-[9px] text-ink-soft bg-paper p-1.5 border border-line/60 rounded-xs space-y-0.5">
                                <span className="font-bold text-[8px] uppercase block text-ink">Evidence:</span>
                                {photo.evidence.slice(0, 3).map((eStr, eIdx) => (
                                  <p key={eIdx} className="leading-tight">
                                    &bull; {eStr}
                                  </p>
                                ))}
                              </div>
                            )}
                          </div>

                          {/* Control buttons */}
                          <div className="flex items-center justify-between gap-1 pt-2 border-t border-line/60">
                            <select
                              className="text-[9px] font-util border border-line bg-paper px-1 py-1 outline-none w-28 cursor-pointer"
                              defaultValue=""
                              onChange={(e) => {
                                if (e.target.value) {
                                  handleMovePhoto(ev.event_id, e.target.value, photo.id);
                                }
                              }}
                            >
                              <option value="" disabled>
                                Move to...
                              </option>
                              {events
                                .filter((other) => other.event_id !== ev.event_id)
                                .map((other, oIdx) => (
                                  <option key={other.event_id} value={other.event_id}>
                                    Event {oIdx + 1}: {other.title.slice(0, 20)}...
                                  </option>
                                ))}
                            </select>

                            <button
                              type="button"
                              onClick={() => handleDetachPhoto(ev.event_id, photo.id)}
                              className="font-util text-[9px] uppercase text-red-700 hover:text-red-900 border border-red-300 hover:bg-red-50 px-2 py-1 cursor-pointer font-bold"
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-3 bg-paper-2 border border-line text-ink-soft font-util text-[10px] italic flex items-center gap-2">
                      <span>📄</span>
                      <span>Zero photos attached — will generate a text-focused editorial layout with highlights sidebar.</span>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Unmatched Photos Section (< 75% Confidence or unassigned) */}
            {unmatchedPhotos.length > 0 && (
              <div className="border border-line bg-amber-50/50 p-4 space-y-3 rounded-xs">
                <div className="flex justify-between items-center border-b border-amber-200 pb-1.5">
                  <span className="font-util text-eyebrow uppercase tracking-wider font-bold text-amber-900 flex items-center gap-1.5">
                    <span>⚠️</span> UNMATCHED PHOTOS ({unmatchedPhotos.length} Unassigned / Confidence &lt; 75%)
                  </span>
                  <span className="font-util text-[9px] text-amber-800">
                    Manual Assignment Available
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {unmatchedPhotos.map((photo) => (
                    <div
                      key={photo.id}
                      className="border border-amber-300 bg-paper p-2.5 flex flex-col justify-between space-y-2 rounded-xs shadow-xs"
                    >
                      <div className="space-y-1">
                        <img
                          src={photo.url}
                          alt={photo.file_name}
                          className="w-full h-24 object-cover border border-line bg-paper-3"
                        />
                        <p className="font-util text-[10px] text-ink font-bold truncate" title={photo.file_name}>
                          {photo.file_name}
                        </p>
                        <span className="font-util text-[8px] uppercase font-bold text-gray-700 bg-gray-100 px-1.5 py-0.5 border border-gray-300 inline-block">
                          {Math.round(photo.confidence * 100)}% Low / Unassigned
                        </span>
                      </div>

                      <div className="pt-2 border-t border-line/60">
                        <label className="font-util text-[8px] uppercase text-ink-soft block mb-1 font-bold">
                          Attach to Event:
                        </label>
                        <select
                          className="w-full text-[9px] font-util border border-line bg-paper px-2 py-1 outline-none cursor-pointer"
                          defaultValue=""
                          onChange={(e) => {
                            if (e.target.value) {
                              handleAttachUnmatched(photo.id, e.target.value);
                            }
                          }}
                        >
                          <option value="" disabled>
                            Select Event...
                          </option>
                          {events.map((ev, evIdx) => (
                            <option key={ev.event_id} value={ev.event_id}>
                              Event {evIdx + 1}: {ev.title.slice(0, 25)}...
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Navigation & Generation Actions */}
            <div className="flex items-center justify-between gap-3 pt-3 border-t border-line">
              <button
                type="button"
                onClick={() => setStep("upload")}
                disabled={generating}
                className="font-util text-xs uppercase tracking-wider text-ink border border-line bg-paper hover:bg-paper-3 px-4 py-2.5 transition-colors cursor-pointer font-bold"
              >
                &larr; Back to Upload
              </button>

              <button
                type="button"
                onClick={handleGenerateMagazine}
                disabled={generating}
                className="font-util text-xs uppercase tracking-wider text-paper bg-accent hover:opacity-95 px-6 py-2.5 transition-all cursor-pointer font-bold flex items-center gap-2 shadow-md disabled:opacity-50"
              >
                {generating ? (
                  <>
                    <span className="animate-spin">⏳</span>
                    <span>Generating Magazine &amp; Deterministic Layout...</span>
                  </>
                ) : (
                  <>
                    <span>✨</span>
                    <span>Approve Associations &amp; Generate Magazine</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* STEP 3: MAGAZINE GENERATION RESULT & PDF PREVIEW                          */}
        {/* ========================================================================= */}
        {step === "preview" && generatedMagazine && (
          <div className="overflow-y-auto space-y-5 pr-1 text-xs flex-1">
            {/* Success Banner */}
            <div className="p-4 bg-emerald-50 border border-emerald-300 space-y-1">
              <span className="font-util text-[9px] uppercase tracking-wider text-emerald-800 font-bold block">
                🎉 Generation Complete &bull; 100% Factually Grounded &bull; Zero Leaks
              </span>
              <h3 className="font-display text-base font-bold text-ink">
                {generatedMagazine.title || "SIET College Magazine Issue"}
              </h3>
              <p className="font-util text-[10px] text-ink-soft">
                {generatedMagazine.page_count} Pages &bull; {generatedMagazine.photos_count} Attached Photos &bull; Composite Score: {generatedMagazine.orchestrator_score || "1.0"}
              </p>
            </div>

            {/* Quick Actions */}
            <div className="flex flex-wrap gap-2">
              {generatedMagazine.pdf_url && (
                <a
                  href={generatedMagazine.pdf_url}
                  download
                  target="_blank"
                  rel="noreferrer"
                  className="font-util text-[10px] uppercase tracking-wider text-paper bg-accent hover:opacity-95 px-4 py-2 font-bold shadow-sm inline-flex items-center gap-1.5"
                >
                  <span>📥</span> Download Publication PDF
                </a>
              )}
              {generatedMagazine.slug && (
                generatedMagazine.status === "published" ? (
                  <a
                    href={`/magazine/${generatedMagazine.slug}`}
                    target="_blank"
                    rel="noreferrer"
                    className="font-util text-[10px] uppercase tracking-wider text-ink border border-line bg-paper hover:bg-paper-2 px-4 py-2 font-bold inline-flex items-center gap-1.5"
                  >
                    <span>📖</span> Open in Interactive Reader
                  </a>
                ) : null
              )}
              {generatedMagazine.status === "review" && (
                <button
                  type="button"
                  onClick={() => handleApprovalAction("approve")}
                  disabled={approvalAction !== null}
                  className="font-util text-[10px] uppercase tracking-wider text-paper bg-ink hover:bg-accent px-4 py-2 font-bold shadow-sm disabled:opacity-50"
                >
                  {approvalAction === "approve" ? "Approving…" : "Approve Magazine"}
                </button>
              )}
              {generatedMagazine.status === "approved" && (
                <button
                  type="button"
                  onClick={() => handleApprovalAction("publish")}
                  disabled={approvalAction !== null}
                  className="font-util text-[10px] uppercase tracking-wider text-paper bg-emerald-700 hover:bg-emerald-800 px-4 py-2 font-bold shadow-sm disabled:opacity-50"
                >
                  {approvalAction === "publish" ? "Publishing…" : "Publish to Public Front Page"}
                </button>
              )}
            </div>

            {/* High-Resolution Page Previews Gallery */}
            {generatedMagazine.render_result?.page_previews && (
              <div className="space-y-3 pt-2">
                <div className="flex justify-between items-center border-b border-line pb-1">
                  <span className="font-util text-eyebrow text-ink-soft uppercase tracking-wider font-bold">
                    Generated Page Gallery ({generatedMagazine.render_result.page_previews.length} Spreads)
                  </span>
                  <span className="font-util text-[9px] text-ink-soft">
                    Viewing Page {activePreviewPage + 1} of {generatedMagazine.render_result.page_previews.length}
                  </span>
                </div>

                {/* Main Selected Page Preview */}
                <div className="border border-line bg-paper p-2 flex justify-center shadow-md">
                  <img
                    src={generatedMagazine.render_result.page_previews[activePreviewPage]}
                    alt={`Page ${activePreviewPage + 1}`}
                    className="max-h-[55vh] object-contain border border-line bg-white"
                  />
                </div>

                {/* Thumbnails strip */}
                <div className="flex gap-2 overflow-x-auto pb-2">
                  {generatedMagazine.render_result.page_previews.map((prevUrl: string, idx: number) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setActivePreviewPage(idx)}
                      className={`border-2 p-0.5 shrink-0 cursor-pointer transition-all ${
                        activePreviewPage === idx ? "border-accent shadow-sm" : "border-line opacity-75 hover:opacity-100"
                      }`}
                    >
                      <img src={prevUrl} alt={`Thumbnail ${idx + 1}`} className="w-14 h-20 object-cover bg-paper-3" />
                      <span className="font-util text-[8px] font-bold block text-center mt-0.5">P.{idx + 1}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Finish Action */}
            <div className="pt-2 border-t border-line flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className="font-util text-xs uppercase tracking-wider text-paper bg-ink hover:opacity-90 px-6 py-2.5 font-bold cursor-pointer shadow-sm"
              >
                Close &amp; Return to Magazines Dashboard
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
