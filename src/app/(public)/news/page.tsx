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
  searchParams: Promise<{ page?: string; department?: string; subcategory?: string; tab?: string; q?: string }>;
}) {
  const params = await searchParams;
  const pageNum = Math.max(1, Number(params.page || "1"));
  const department = params.department || "";
  const subcategory = params.subcategory || "";
  const tab = params.tab || ""; // "" or "today" (default: Today's news), "all_active", "latest"
  const searchQuery = params.q || "";

  const dateFilter = tab === "all_active" ? "all" : "today";

  let newsItems: NewsItem[] = [];
  let currentPage = pageNum;
  let totalPages = 1;
  let totalItems = 0;
  let isFallback = false;
  let deptCounts: Record<string, number> = {};
  let totalAllCount = 0;

  try {
    const taxonomyRes = await api.newsTaxonomy(`?date_filter=${dateFilter}`);
    if (taxonomyRes && taxonomyRes.departments) {
      deptCounts = taxonomyRes.departments;
      totalAllCount = Number(Object.values(taxonomyRes.departments).reduce((a: any, b: any) => Number(a) + Number(b), 0));
    }
  } catch (err) {
    console.warn("News taxonomy fetch error:", err);
  }

  try {
    const queryParams = new URLSearchParams();
    if (pageNum > 1) queryParams.set("page", String(pageNum));
    if (department) queryParams.set("department", department);
    if (subcategory) queryParams.set("subcategory", subcategory);
    if (tab) queryParams.set("tab", tab);
    if (searchQuery) queryParams.set("q", searchQuery);
    queryParams.set("date_filter", dateFilter);

    const queryString = queryParams.toString();
    const res = await api.news(queryString ? `?${queryString}` : "");

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
    if (tab) p.set("tab", tab);
    if (searchQuery) p.set("q", searchQuery);
    const qs = p.toString();
    return `/news${qs ? `?${qs}` : ""}`;
  };

  const getTabHref = (tabName: string) => {
    const p = new URLSearchParams();
    if (tabName) p.set("tab", tabName);
    if (department) p.set("department", department);
    if (searchQuery) p.set("q", searchQuery);
    const qs = p.toString();
    return `/news${qs ? `?${qs}` : ""}`;
  };

  return (
    <main className="kitchen-page">
      {isFallback && (
        <div className="bg-amber-500 text-black px-4 py-2.5 text-center text-sm font-semibold select-none rounded mb-6">
          ⚠ Live news API offline — check backend connection
        </div>
      )}

      {/* Header */}
      <header className="flex flex-col gap-2 reveal">
        <p className="eyebrow">Tech & Lab News · Daily Edition</p>
        <h1 className="font-display text-h1 font-semibold leading-tight text-ink">
          SIET News
        </h1>
        <p className="font-util text-xs text-ink-soft">
          {tab === "all_active"
            ? "Displaying all active non-archived news releases"
            : "Showing today's fresh verified news updates"}
        </p>
      </header>

      {/* Single Department Filter Row with Live Counts (matches /articles pill filter style) */}
      <div className="reveal">
        <DomainFilter
          domains={departmentDomains}
          activeSlug={department}
          hrefBuilder={getDepartmentFilterHref}
          totalCount={totalAllCount || totalItems}
        />
      </div>

      {/* Feed Filters & Scope Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-3 reveal">
        <div className="flex items-center gap-6">
          <Link
            href={getTabHref("")}
            className={`font-util text-eyebrow tracking-[0.14em] uppercase transition-colors pb-1 border-b-2 ${
              !tab || tab === "today" ? "border-accent text-accent font-bold" : "border-transparent text-ink-soft hover:text-ink"
            }`}
          >
            Today&apos;s News ({totalItems})
          </Link>
          <Link
            href={getTabHref("all_active")}
            className={`font-util text-eyebrow tracking-[0.14em] uppercase transition-colors pb-1 border-b-2 ${
              tab === "all_active" ? "border-accent text-accent font-bold" : "border-transparent text-ink-soft hover:text-ink"
            }`}
          >
            All Active Feed
          </Link>
          <Link
            href={getTabHref("latest")}
            className={`font-util text-eyebrow tracking-[0.14em] uppercase transition-colors pb-1 border-b-2 ${
              tab === "latest" ? "border-accent text-accent font-bold" : "border-transparent text-ink-soft hover:text-ink"
            }`}
          >
            Latest
          </Link>
        </div>

        <div className="flex items-center gap-4">
          {department && (
            <span className="font-util text-eyebrow text-ink-soft">
              Active Dept: <strong className="text-accent">{department.toUpperCase()}</strong>
            </span>
          )}
          <Link
            href="/news/archive"
            className="font-util text-eyebrow text-ink-soft hover:text-accent transition-colors flex items-center gap-1"
          >
            <span>📦</span> Archive Vault
          </Link>
        </div>
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
          message={
            department
              ? `No articles currently cataloged for department '${department}'.`
              : "No news updates available in the index for today."
          }
          actionHref={getTabHref("all_active")}
          actionLabel="Browse All Active Feed"
        />
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center pt-8 border-t border-line">
          <Pagination
            page={currentPage}
            pages={totalPages}
            basePath={getTabHref(tab)}
          />
        </div>
      )}
    </main>
  );
}
