import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { ContentCard, DomainFilter, Pagination, EmptyState } from "@/components/shared";
import { NewsSearchInput } from "@/components/news/NewsSearchInput";
import type { NewsItem, Domain } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function NewsPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; department?: string; subcategory?: string; q?: string }>;
}) {
  const params = await searchParams;
  const pageNum = Math.max(1, Number(params.page || "1"));
  const department = params.department || "";
  const subcategory = params.subcategory || "";
  const searchQuery = params.q || "";

  let newsItems: NewsItem[] = [];
  let currentPage = pageNum;
  let totalPages = 1;
  let totalItems = 0;

  let isFallback = false;
  let deptCounts: Record<string, number> = {};
  let totalAllCount = 0;

  // 1. Fetch Taxonomy Pills across 90-day active feed
  try {
    const taxonomyRes = await api.newsTaxonomy("?date_filter=all");
    if (taxonomyRes && taxonomyRes.departments) {
      deptCounts = taxonomyRes.departments;
      totalAllCount = Number(
        Object.values(taxonomyRes.departments).reduce((a: any, b: any) => Number(a) + Number(b), 0)
      );
    }
  } catch (err) {
    console.warn("News taxonomy fetch error:", err);
  }

  // 2. Fetch Single Unified News Feed Data
  try {
    const p = new URLSearchParams();
    p.set("page", String(pageNum));
    p.set("limit", "20");
    if (department) p.set("department", department);
    if (subcategory) p.set("subcategory", subcategory);
    if (searchQuery) p.set("q", searchQuery);

    const res = await api.news(`?${p.toString()}`);
    newsItems = res.items || [];
    currentPage = res.page || 1;
    totalPages = res.pages || 1;
    totalItems = res.total || 0;
  } catch (error) {
    console.error("News API request failed:", error);
    isFallback = true;
  }

  const departmentDomains: Domain[] = [
    { slug: "ai-ml", name: "AI / ML", count: deptCounts["ai-ml"] || 0 },
    { slug: "cybersecurity", name: "Cybersecurity", count: deptCounts["cybersecurity"] || 0 },
    { slug: "pcb-electronics", name: "PCB / Electronics", count: deptCounts["pcb-electronics"] || 0 },
    { slug: "vlsi-semiconductor", name: "VLSI / Semiconductor", count: deptCounts["vlsi-semiconductor"] || 0 },
    { slug: "robotics", name: "Robotics", count: deptCounts["robotics"] || 0 },
    { slug: "ar-vr-xr", name: "AR / VR / XR", count: deptCounts["ar-vr-xr"] || 0 },
    { slug: "iot", name: "IoT", count: deptCounts["iot"] || 0 },
  ];

  const getDepartmentFilterHref = (deptSlug: string) => {
    const p = new URLSearchParams();
    if (deptSlug) p.set("department", deptSlug);
    if (searchQuery) p.set("q", searchQuery);
    const qs = p.toString();
    return `/news${qs ? `?${qs}` : ""}`;
  };

  const getPaginationHref = (pageNumber: number) => {
    const p = new URLSearchParams();
    if (pageNumber > 1) p.set("page", String(pageNumber));
    if (department) p.set("department", department);
    if (searchQuery) p.set("q", searchQuery);
    const qs = p.toString();
    return `/news${qs ? `?${qs}` : ""}`;
  };

  return (
    <main className="kitchen-page !gap-y-6">
      {isFallback && (
        <div className="bg-amber-500 text-black px-4 py-2.5 text-center text-sm font-semibold select-none rounded">
          ⚠ Live news API offline — check backend connection
        </div>
      )}

      {/* Masthead Control Cluster */}
      <div className="space-y-4">
        {/* Masthead Header */}
        <header className="flex flex-col gap-3 reveal">
          <p className="eyebrow">Tech &amp; Lab News · 90-Day Rolling Index</p>
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <h1 className="font-display text-h1 font-semibold leading-tight text-ink">
                SIET News
              </h1>
              <p className="font-util text-xs text-ink-soft mt-1">
                Real-time engineering bulletins, research papers, and technology updates (0–90 days)
              </p>
            </div>
            <Link
              href="/news/archive"
              className="font-util text-eyebrow text-ink-soft hover:text-accent transition-colors flex items-center gap-1.5 self-start md:self-auto border border-line px-3 py-1.5 bg-paper hover:bg-paper-2"
            >
              <span>📦</span> Archive Vault (90+ Days)
            </Link>
          </div>
        </header>

        {/* Interactive Debounced Search Bar */}
        <div className="reveal">
          <React.Suspense fallback={<div className="h-10 w-full max-w-2xl bg-paper-2 border border-line rounded-sm" />}>
            <NewsSearchInput department={department} />
          </React.Suspense>
        </div>

        {/* Single Department Filter Row with Live Counts across 90-day active feed */}
        <div className="reveal pt-1">
          <DomainFilter
            domains={departmentDomains}
            activeSlug={department}
            hrefBuilder={getDepartmentFilterHref}
            totalCount={totalAllCount}
          />
        </div>
      </div>

      {/* UNIFIED NEWS FEED SECTION */}
      <section className="space-y-6 reveal">
        <div className="flex items-center justify-between border-b border-line pb-3">
          <div>
            <p className="font-util text-eyebrow text-accent uppercase tracking-wider">
              {searchQuery ? "Search Query Active" : "Unified Engineering Feed"}
            </p>
            <h2 className="font-display text-h2 font-semibold text-ink">
              {searchQuery
                ? `Results for “${searchQuery}” (${totalItems} found)`
                : `News (${totalItems} Articles)`}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            {department && (
              <span className="font-util text-eyebrow text-ink-soft">
                Filtered: <strong className="text-accent">{department.toUpperCase()}</strong>
              </span>
            )}
            {searchQuery && (
              <Link
                href={getDepartmentFilterHref(department)}
                className="font-util text-eyebrow text-ink-soft hover:text-ink uppercase tracking-wider underline"
              >
                Clear Search [×]
              </Link>
            )}
          </div>
        </div>

        {newsItems.length > 0 ? (
          <>
            <div className="card-grid">
              {newsItems.map((item) => (
                <ContentCard key={item.id} variant="news" item={item} />
              ))}
            </div>

            {totalPages > 1 && (
              <div className="flex justify-center pt-8 border-t border-line">
                <Pagination
                  page={currentPage}
                  pages={totalPages}
                  basePath={getPaginationHref(currentPage).replace(/page=\d+/, "")}
                />
              </div>
            )}
          </>
        ) : (
          <EmptyState
            message={
              searchQuery
                ? `No active news articles matched your search query "${searchQuery}".`
                : department
                ? `No active news articles cataloged for department '${department}'.`
                : "No active news articles available in the 90-day index."
            }
            actionHref={getDepartmentFilterHref("")}
            actionLabel="View All News"
          />
        )}
      </section>
    </main>
  );
}
