import * as React from "react";
import { api } from "@/lib/api";
import { ContentCard, DomainFilter, Pagination, EmptyState, ErrorState } from "@/components/shared";
import type { Article, Domain } from "@/lib/types";

type SearchParams = Promise<{
  domain?: string;
  page?: string;
}>;

export default async function ArticlesPage(props: { searchParams: SearchParams }) {
  const searchParams = await props.searchParams;
  const activeDomain = searchParams.domain || "";
  const pageNum = parseInt(searchParams.page || "1", 10);

  let domains: Domain[] = [];
  let articles: Article[] = [];
  let currentPage = pageNum;
  let totalPages = 1;
  let loadError: string | null = null;

  try {
    domains = await api.domains().catch(() => []);
  } catch {
    domains = [];
  }

  try {
    if (activeDomain) {
      const res = await api.articlesByDomain(activeDomain);
      articles = res.items ?? [];
      currentPage = res.page ?? 1;
      totalPages = res.pages ?? 1;
    } else {
      const q = `?page=${pageNum}`;
      const res = await api.articles(q);
      articles = res.items ?? [];
      currentPage = res.page ?? 1;
      totalPages = res.pages ?? 1;
    }
  } catch (error: any) {
    loadError = error?.message || "Failed to load research articles from backend API.";
  }

  const getDomainFilterHref = (domainSlug: string) => {
    return domainSlug ? `/articles?domain=${domainSlug}` : "/articles";
  };

  return (
    <main className="kitchen-page">
      <header className="flex flex-col gap-2 reveal">
        <p className="eyebrow">Student Writing</p>
        <h1 className="font-display text-h1 font-semibold leading-tight text-ink">
          Articles & Notes
        </h1>
      </header>

      {/* Domain Filter Row */}
      {domains.length > 0 && (
        <div className="reveal">
          <DomainFilter
            domains={domains}
            activeSlug={activeDomain}
            hrefBuilder={getDomainFilterHref}
          />
        </div>
      )}

      {loadError ? (
        <ErrorState title="Failed to Load Articles" message={loadError} />
      ) : articles.length > 0 ? (
        <div className="card-grid">
          {articles.map((item) => (
            <ContentCard key={item.id} variant="article" item={item} />
          ))}
        </div>
      ) : (
        <EmptyState actionHref="/articles" actionLabel="View all articles" />
      )}

      {/* Pagination */}
      {totalPages > 1 && !loadError && (
        <div className="flex justify-center pt-8 border-t border-line">
          <Pagination
            page={currentPage}
            pages={totalPages}
            basePath={activeDomain ? `/articles?domain=${activeDomain}` : "/articles"}
          />
        </div>
      )}
    </main>
  );
}
