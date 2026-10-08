"use client";

import * as React from "react";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { MagazineIssue } from "@/lib/types";

export function MagazineViewer({ issue }: { issue: MagazineIssue }) {
  const [currentPageNum, setCurrentPageNum] = useState(1);
  const [showAccessibleText, setShowAccessibleText] = useState(false);
  // Optional page-flip animation state. There is currently NO animated
  // template spec in the repo (no animation/motion/flip fields on
  // MagazineTemplate, TemplateVersion, TemplatePage, TemplateRegion,
  // template_metadata, style_rules, section_schema, or the SIET_DEFAULT_V1
  // spec), so this stays OFF unless a page opts in via
  // data-magazine-animation="page-flip".
  const [flipKey, setFlipKey] = useState(0);
  const [flipDir, setFlipDir] = useState<"next" | "prev" | null>(null);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const animationEnabled =
    !prefersReducedMotion &&
    typeof document !== "undefined" &&
    document.querySelector('[data-magazine-animation="page-flip"]') !== null;

  const downloadUrl = api.magDownloadUrl(issue.slug);

  const pages = issue.pages || [];
  const tocEntries = issue.tocEntries || [];
  const totalPages: number = pages.length > 0 ? pages.length : (issue.pageCount || 0);

  const currentPage = pages.find((p) => p.pageNumber === currentPageNum) || pages[0];

  const handlePrev = () => {
    if (currentPageNum > 1) {
      setFlipDir("prev");
      setFlipKey((k) => k + 1);
      setCurrentPageNum((p) => p - 1);
    }
  };

  const handleNext = () => {
    if (currentPageNum < totalPages) {
      setFlipDir("next");
      setFlipKey((k) => k + 1);
      setCurrentPageNum((p) => p + 1);
    }
  };

  // Keyboard Navigation (Left / Right Arrow Keys)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") handlePrev();
      if (e.key === "ArrowRight") handleNext();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentPageNum, totalPages]);

  return (
    <div className="space-y-6">
      {/* Top Toolbar */}
      <div className="bg-paper-2 border border-line p-4 flex flex-wrap items-center justify-between gap-4 sticky top-14 z-20 shadow-xs">
        {/* Table of Contents Jump Selector */}
        <div className="flex items-center gap-2">
          <label className="font-util text-eyebrow text-ink-soft uppercase tracking-wider hidden sm:inline-block">
            Table of Contents:
          </label>
          <select
            value={currentPageNum}
            onChange={(e) => setCurrentPageNum(Number(e.target.value))}
            className="border border-line bg-paper px-3 py-1.5 text-xs font-sans text-ink outline-none focus:border-ink cursor-pointer max-w-xs truncate"
          >
            {tocEntries.length > 0
              ? tocEntries.map((toc) => (
                <option key={toc.id || toc.pageNumber} value={toc.pageNumber}>
                  Page {toc.pageNumber}: {toc.heading}
                </option>
              ))
              : Array.from({ length: totalPages }, (_, i) => (
                <option key={i + 1} value={i + 1}>
                  Page {i + 1}
                </option>
              ))}
          </select>
        </div>

        {/* Page Nav Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={handlePrev}
            disabled={currentPageNum <= 1}
            className="font-util text-eyebrow uppercase tracking-wider text-ink border border-line bg-paper px-3 py-1.5 hover:bg-paper-3 transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            ← Prev Page
          </button>

          <span className="font-util text-xs font-semibold text-ink px-2">
            {currentPageNum} / {totalPages || 1}
          </span>

          <button
            onClick={handleNext}
            disabled={currentPageNum >= totalPages}
            className="font-util text-eyebrow uppercase tracking-wider text-ink border border-line bg-paper px-3 py-1.5 hover:bg-paper-3 transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            Next Page →
          </button>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowAccessibleText(!showAccessibleText)}
            className="font-util text-[10px] uppercase tracking-wider text-ink-soft hover:text-ink border border-line px-3 py-1.5 bg-paper transition-colors cursor-pointer"
          >
            {showAccessibleText ? "Hide Plain Text" : "Show Page Text"}
          </button>

          <a
            href={downloadUrl}
            download={`${issue.slug}.pdf`}
            className="font-util text-eyebrow uppercase tracking-wider text-paper bg-ink hover:bg-accent border border-ink px-3 py-1.5 transition-colors cursor-pointer flex items-center gap-1.5"
          >
            <span>Download Issue</span>
            <span>↓</span>
          </a>
        </div>
      </div>

      {/* Main Page Display Canvas */}
      <div className="border border-line bg-paper-3 p-4 sm:p-8 flex justify-center items-center min-h-[600px] shadow-inner relative overflow-hidden [perspective:1600px]">
        {currentPage?.imageUrl ? (
          <img
            key={animationEnabled ? `${flipKey}-${currentPageNum}` : currentPageNum}
            src={currentPage.imageUrl}
            alt={`${issue.title} - Page ${currentPageNum}`}
            style={
              animationEnabled && flipDir
                ? { transformOrigin: flipDir === "next" ? "left center" : "right center" }
                : undefined
            }
            className={`max-w-full max-h-[85vh] object-contain border border-line shadow-md bg-paper transition-all duration-200 ${
              animationEnabled && flipDir ? "magazine-page-flip" : ""
            } ${animationEnabled && flipDir === "next" ? "magazine-page-flip-next" : ""} ${
              animationEnabled && flipDir === "prev" ? "magazine-page-flip-prev" : ""
            }`}
          />
        ) : (
          <div className="p-12 text-center space-y-3 bg-paper border border-line max-w-md">
            <p className="font-display text-sm font-semibold text-ink">Page Image Preview</p>
            <p className="font-body text-xs text-ink-soft">
              Page {currentPageNum} is available in original PDF format.
            </p>
          </div>
        )}
      </div>

      {/* Accessible Text Layer / Plain Text Viewer (SEO & Screen Readers) */}
      <div className={showAccessibleText ? "block" : "sr-only"}>
        <div className="border border-line bg-paper p-6 space-y-3">
          <h3 className="font-util text-eyebrow text-ink-soft uppercase tracking-wider border-b border-line pb-2">
            Accessible Page Text (Page {currentPageNum})
          </h3>
          <div className="font-body text-xs text-ink whitespace-pre-wrap leading-relaxed max-w-3xl">
            {currentPage?.extractedText ? (
              currentPage.extractedText
            ) : (
              <span className="italic text-ink-soft">No extractable text on this page.</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
