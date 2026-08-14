import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Pagination, EmptyState, TagChip } from "@/components/shared";
import type { MagazineIssue } from "@/lib/types";

const FREQUENCIES = [
  { label: "All Editions", value: "" },
  { label: "Monthly", value: "monthly" },
  { label: "Quarterly", value: "quarterly" },
  { label: "Annual", value: "annual" },
  { label: "Special", value: "special" },
];

type SearchParams = Promise<{
  type?: string;
  year?: string;
  page?: string;
}>;

export default async function MagazinePage(props: { searchParams: SearchParams }) {
  const searchParams = await props.searchParams;
  const activeType = searchParams.type || "";
  const activeYear = searchParams.year || "";
  const pageNum = parseInt(searchParams.page || "1", 10);

  let issues: MagazineIssue[] = [];
  let currentPage = pageNum;
  let totalPages = 1;

  try {
    const q = `?page=${pageNum}${activeType ? `&type=${activeType}` : ""}${activeYear ? `&year=${activeYear}` : ""}`;
    const res = await api.magazine(q);
    issues = res.items ?? [];
    currentPage = res.page ?? 1;
    totalPages = res.pages ?? 1;
  } catch (error) {
    console.error("Magazine API request error:", error);
    issues = [];
  }

  const buildHref = (key: string, value: string) => {
    const params = new URLSearchParams();
    if (key === "type") {
      if (value) params.set("type", value);
      if (activeYear) params.set("year", activeYear);
    } else if (key === "year") {
      if (activeType) params.set("type", activeType);
      if (value) params.set("year", value);
    }
    const qs = params.toString();
    return `/magazine${qs ? `?${qs}` : ""}`;
  };

  return (
    <main className="kitchen-page space-y-8">
      {/* Editorial Header */}
      <header className="flex flex-col gap-2 border-b border-line pb-6 reveal">
        <div className="flex items-center justify-between">
          <p className="eyebrow">SIET Publications</p>
          <span className="font-util text-[10px] uppercase tracking-wider text-ink-soft bg-paper-3 px-2 py-0.5 border border-line">
            Official College Issues
          </span>
        </div>
        <h1 className="font-display text-h1 font-semibold leading-tight text-ink">
          SIET Tech Magazine &amp; Newsletters
        </h1>
        <p className="font-body text-body text-ink-soft max-w-2xl mt-1">
          Explore curated campus research digests, department innovations, and technical publications in high-fidelity interactive digital issues.
        </p>
      </header>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 py-3 border-b border-line">
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-util text-eyebrow text-ink-soft uppercase">Edition:</span>
          <div className="flex flex-wrap gap-2">
            {FREQUENCIES.map((f) => (
              <TagChip
                key={f.value}
                active={activeType === f.value}
                label={f.label}
                href={buildHref("type", f.value)}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Issue Listing Grid */}
      {issues.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {issues.map((issue) => (
            <article
              key={issue.id}
              className="border border-line bg-paper hover:shadow-md transition-all flex flex-col justify-between group overflow-hidden"
            >
              <div>
                {/* Cover Image Container */}
                <Link href={`/magazine/${issue.slug}`} className="block relative bg-paper-3 border-b border-line aspect-[3/4] overflow-hidden">
                  {issue.coverImageUrl ? (
                    <img
                      src={issue.coverImageUrl}
                      alt={issue.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center bg-paper-2">
                      <span className="font-display text-h3 font-semibold text-ink-soft">SIET</span>
                      <span className="font-util text-[10px] uppercase tracking-wider text-ink-soft mt-1">
                        Tech Digest
                      </span>
                    </div>
                  )}
                  <div className="absolute top-3 right-3 bg-ink text-paper font-util text-[9px] uppercase tracking-wider px-2 py-1 shadow-xs">
                    {(issue.pageCount || 0) > 0 ? `${issue.pageCount} Pages` : "PDF Issue"}
                  </div>
                </Link>

                {/* Content Details */}
                <div className="p-6 space-y-3">
                  <div className="flex items-center gap-2 font-util text-[10px] uppercase tracking-wider text-ink-soft">
                    <span className="text-accent font-semibold">{issue.type}</span>
                    <span>·</span>
                    <span>
                      {new Date(issue.issueDate || Date.now()).toLocaleDateString("en-US", {
                        month: "short",
                        year: "numeric",
                      })}
                    </span>
                  </div>

                  <h2 className="font-display text-h3 font-semibold text-ink group-hover:text-accent transition-colors leading-snug">
                    <Link href={`/magazine/${issue.slug}`}>{issue.title}</Link>
                  </h2>

                  {issue.description && (
                    <p className="font-body text-body-sm text-ink-soft line-clamp-3 leading-relaxed">
                      {issue.description}
                    </p>
                  )}
                </div>
              </div>

              {/* Action Link Footer */}
              <div className="px-6 pb-6 pt-2 border-t border-line/50 flex justify-between items-center bg-paper-2">
                <Link
                  href={`/magazine/${issue.slug}`}
                  className="font-util text-eyebrow uppercase tracking-wider text-ink group-hover:text-accent flex items-center gap-1.5 transition-colors font-semibold"
                >
                  Read Interactive Issue →
                </Link>

                {issue.pdfUrl && (
                  <a
                    href={issue.pdfUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-util text-[10px] text-ink-soft hover:text-ink uppercase tracking-wider underline"
                  >
                    PDF Direct
                  </a>
                )}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState actionHref="/magazine" actionLabel="View all issues" />
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center pt-8 border-t border-line">
          <Pagination page={currentPage} pages={totalPages} basePath="/magazine" />
        </div>
      )}
    </main>
  );
}
