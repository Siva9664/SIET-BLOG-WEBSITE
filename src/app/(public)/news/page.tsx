import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { ContentCard, DomainFilter, Pagination, EmptyState } from "@/components/shared";
import type { NewsItem, Domain } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function NewsPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; domain?: string; tab?: string }>;
}) {
  const params = await searchParams;
  const pageNum = Math.max(1, Number(params.page || "1"));
  const activeDomain = params.domain || "";
  const tab = params.tab || ""; // "latest" | "trending" | ""

  let domains: Domain[] = [];
  try {
    domains = await api.domains();
  } catch (error) {
    console.error("Failed to load domains from backend API:", error);
    domains = [];
  }

  let newsItems: NewsItem[] = [];
  let currentPage = pageNum;
  let totalPages = 1;
  let isPaginated = true;

  try {
    const queryParams = new URLSearchParams();
    if (pageNum > 1) queryParams.set("page", String(pageNum));
    if (activeDomain) queryParams.set("domain", activeDomain);
    if (tab) queryParams.set("tab", tab);

    const queryString = queryParams.toString();
    const res = await api.news(queryString ? `?${queryString}` : "");

    newsItems = res.items || [];
    currentPage = res.page || 1;
    totalPages = res.pages || 1;

    if (tab === "latest" || tab === "trending") {
      isPaginated = false;
    }
  } catch (error) {
    console.error("News API request failed:", error);
    newsItems = [];
    currentPage = 1;
    totalPages = 1;
  }

  // URL Path builders preserving both tab and domain
  const getTabHref = (tabName: string) => {
    const p = new URLSearchParams();
    if (tabName) p.set("tab", tabName);
    if (activeDomain) p.set("domain", activeDomain);
    const qs = p.toString();
    return `/news${qs ? `?${qs}` : ""}`;
  };

  const getDomainHref = (domainSlug: string) => {
    const p = new URLSearchParams();
    if (tab) p.set("tab", tab);
    if (domainSlug) p.set("domain", domainSlug);
    const qs = p.toString();
    return `/news${qs ? `?${qs}` : ""}`;
  };

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-10">
      {/* Header */}
      <header className="flex flex-col gap-2 reveal">
        <p className="font-util text-eyebrow text-accent uppercase tracking-widest">
          SIET News Pipeline
        </p>
        <h1 className="font-display text-h1 text-ink font-bold tracking-tight">
          Today's Headlines
        </h1>
        <p className="font-sans text-body text-ink-soft max-w-2xl">
          Live automated news research, technological developments, and research updates aggregated directly from global engineering feeds.
        </p>
      </header>

      {/* Tabs */}
      <div className="flex items-center gap-6 border-b border-line pb-4 reveal">
        <Link
          href={getTabHref("")}
          className={`font-util text-xs uppercase tracking-wider transition-colors pb-1 ${
            !tab ? "text-accent border-b-2 border-accent font-semibold" : "text-ink-soft hover:text-ink"
          }`}
        >
          All News
        </Link>
        <Link
          href={getTabHref("latest")}
          className={`font-util text-xs uppercase tracking-wider transition-colors pb-1 ${
            tab === "latest" ? "text-accent border-b-2 border-accent font-semibold" : "text-ink-soft hover:text-ink"
          }`}
        >
          Latest
        </Link>
        <Link
          href={getTabHref("trending")}
          className={`font-util text-xs uppercase tracking-wider transition-colors pb-1 ${
            tab === "trending" ? "text-accent border-b-2 border-accent font-semibold" : "text-ink-soft hover:text-ink"
          }`}
        >
          Trending
        </Link>
      </div>

      {/* Domain Filters */}
      {domains.length > 0 && (
        <section className="reveal">
          <DomainFilter
            domains={domains}
            activeSlug={activeDomain}
            hrefBuilder={getDomainHref}
          />
        </section>
      )}

      {/* Articles Grid */}
      {newsItems.length > 0 ? (
        <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 reveal">
          {newsItems.map((item) => (
            <ContentCard key={item.id} item={item} variant="news" />
          ))}
        </section>
      ) : (
        <section className="reveal">
          <EmptyState
            message={
              activeDomain
                ? "No articles matched the selected filter combination."
                : "No news articles are available currently."
            }
            actionHref="/news"
            actionLabel="Clear filters"
          />
        </section>
      )}

      {/* Pagination */}
      {isPaginated && totalPages > 1 && (
        <section className="flex justify-center pt-6 reveal">
          <Pagination
            page={currentPage}
            pages={totalPages}
            basePath={
              activeDomain ? `/news?domain=${activeDomain}` : "/news"
            }
          />
        </section>
      )}
    </main>
  );
}
