import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { ContentCard, Pagination, EmptyState, Breadcrumb } from "@/components/shared";
import type { NewsItem } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function NewsArchivePage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; department?: string; q?: string }>;
}) {
  const params = await searchParams;
  const pageNum = Math.max(1, Number(params.page || "1"));
  const department = params.department || "";
  const searchQuery = params.q || "";

  let newsItems: NewsItem[] = [];
  let currentPage = pageNum;
  let totalPages = 1;
  let totalItems = 0;
  let isFallback = false;

  try {
    const queryParams = new URLSearchParams();
    if (pageNum > 1) queryParams.set("page", String(pageNum));
    if (department) queryParams.set("department", department);
    if (searchQuery) queryParams.set("q", searchQuery);

    const queryString = queryParams.toString();
    const res = await api.newsArchived(queryString ? `?${queryString}` : "");

    newsItems = res.items || [];
    currentPage = res.page || 1;
    totalPages = res.pages || 1;
    totalItems = res.total || 0;
  } catch (error) {
    console.error("Archived News API request failed:", error);
    isFallback = true;
  }

  return (
    <main className="kitchen-page">
      {isFallback && (
        <div className="bg-amber-500 text-black px-4 py-2.5 text-center text-sm font-semibold select-none rounded mb-6">
          ⚠ Live news API offline — check backend connection
        </div>
      )}

      {/* Header & Breadcrumb */}
      <header className="flex flex-col gap-3 reveal">
        <Breadcrumb
          items={[
            { label: "Home", href: "/" },
            { label: "SIET News", href: "/news" },
            { label: "News Archive" },
          ]}
        />
        <div className="flex flex-col gap-1">
          <p className="eyebrow text-amber-700 dark:text-amber-400">Historical Coverage</p>
          <h1 className="font-display text-h1 font-semibold leading-tight text-ink">
            Archived Tech News
          </h1>
        </div>
        <p className="text-ink-soft text-body max-w-2xl">
          Historical technology news and lab updates older than 30 days — permanently preserved in the SIET Knowledge Base with zero deletions.
        </p>
      </header>

      {/* Archive Status Banner */}
      <div className="rounded-lg border border-line bg-line/20 p-4 flex flex-wrap items-center justify-between gap-4 reveal">
        <div className="flex items-center gap-3">
          <span className="text-xl">📦</span>
          <div>
            <p className="font-util text-eyebrow font-bold text-ink uppercase tracking-wider">
              Permanent Knowledge Vault
            </p>
            <p className="text-xs text-ink-soft">
              {totalItems} article{totalItems === 1 ? "" : "s"} archived in historical repository
            </p>
          </div>
        </div>
        <Link
          href="/news"
          className="px-3.5 py-1.5 bg-accent/10 hover:bg-accent/20 text-accent border border-accent/30 text-xs font-util font-bold rounded transition-colors"
        >
          ← Return to Live News Feed
        </Link>
      </div>

      {/* News Articles Grid */}
      {newsItems.length > 0 ? (
        <div className="card-grid">
          {newsItems.map((item) => (
            <ContentCard key={item.id} variant="news" item={item} />
          ))}
        </div>
      ) : (
        <EmptyState
          message="No archived news articles currently in the historical index."
          actionHref="/news"
          actionLabel="View Current News Feed"
        />
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center pt-8 border-t border-line">
          <Pagination
            page={currentPage}
            pages={totalPages}
            basePath="/news/archive"
          />
        </div>
      )}
    </main>
  );
}
