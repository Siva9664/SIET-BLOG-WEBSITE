"use client";

import * as React from "react";
import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Breadcrumb, ContentCard, EmptyState, TagChip, LoadingSkeleton, ErrorState } from "@/components/shared";
import type { NewsItem, Article, Achievement, Domain } from "@/lib/types";

const SUGGESTIONS = [
  "Machine Learning",
  "Robotics",
  "RAG",
  "Hackathon",
  "LiDAR",
  "Ethics",
];

function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const query = searchParams.get("q") || "";

  const [inputVal, setInputVal] = useState(query);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [domains, setDomains] = useState<Domain[]>([]);

  // Results State
  const [news, setNews] = useState<NewsItem[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [achievements, setAchievements] = useState<Achievement[]>([]);

  // Filtering State
  const [selectedType, setSelectedType] = useState<string>("all");
  const [selectedDomain, setSelectedDomain] = useState<string>("all");

  // Fetch domains on mount
  useEffect(() => {
    api.domains()
      .then((res) => setDomains(res || []))
      .catch(() => setDomains([]));
  }, []);

  // Sync state if URL param updates
  useEffect(() => {
    setInputVal(query);
  }, [query]);

  const executeSearch = (q: string) => {
    if (!q.trim()) {
      setNews([]);
      setArticles([]);
      setAchievements([]);
      return;
    }

    setLoading(true);
    setLoadError(null);

    api.search(q)
      .then((res: any) => {
        setNews(res?.news || []);
        setArticles(res?.articles || []);
        setAchievements(res?.achievements || []);
      })
      .catch((err: any) => {
        setNews([]);
        setArticles([]);
        setAchievements([]);
        setLoadError(err?.message || "Failed to search backend index.");
      })
      .finally(() => setLoading(false));
  };

  // Execute Search
  useEffect(() => {
    executeSearch(query);
  }, [query]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    router.push(`/search?q=${encodeURIComponent(inputVal)}`);
  };

  const handleSuggestionClick = (term: string) => {
    setInputVal(term);
    router.push(`/search?q=${encodeURIComponent(term)}`);
  };

  // Filter items client-side
  const filterByDomain = (item: { domain: Domain }) => {
    if (selectedDomain === "all") return true;
    return item.domain?.slug === selectedDomain;
  };

  const filteredNews = news.filter(filterByDomain);
  const filteredArticles = articles.filter(filterByDomain);
  const filteredAchievements = achievements.filter(filterByDomain);

  const hasNews = (selectedType === "all" || selectedType === "news") && filteredNews.length > 0;
  const hasArticles = (selectedType === "all" || selectedType === "articles") && filteredArticles.length > 0;
  const hasAchievements = (selectedType === "all" || selectedType === "achievements") && filteredAchievements.length > 0;

  const totalResults =
    (selectedType === "all" || selectedType === "news" ? filteredNews.length : 0) +
    (selectedType === "all" || selectedType === "articles" ? filteredArticles.length : 0) +
    (selectedType === "all" || selectedType === "achievements" ? filteredAchievements.length : 0);

  return (
    <main className="kitchen-page">
      {/* Header */}
      <header className="space-y-4">
        <Breadcrumb items={[{ label: "Home", href: "/" }, { label: "Search" }]} />
        <h1 className="font-display text-h1 font-semibold leading-tight text-ink">
          Search Directory
        </h1>
      </header>

      {/* Search Input Bar */}
      <form onSubmit={handleSearchSubmit} className="search-bar">
        <label className="sr-only" htmlFor="site-search-input">
          Search
        </label>
        <input
          id="site-search-input"
          type="search"
          placeholder="Search news, articles, or achievements..."
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
        />
        <button type="submit">Search</button>
      </form>

      {/* Suggestion Chips (when query is empty) */}
      {!query.trim() && (
        <div className="space-y-3 pt-4">
          <p className="font-util text-eyebrow text-ink-soft uppercase tracking-wider">
            Suggested Search Queries
          </p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((term) => (
              <button
                key={term}
                onClick={() => handleSuggestionClick(term)}
                className="border border-line bg-paper-2 hover:border-accent hover:text-accent transition-colors px-3 py-1 text-xs font-util uppercase tracking-wider"
              >
                {term}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Query Results / Filter Section */}
      {query.trim() && (
        <div className="space-y-8 pt-4">
          {loadError ? (
            <ErrorState title="Search Failed" message={loadError} onRetry={() => executeSearch(query)} />
          ) : (
            <>
              {/* Filters Bar */}
              <div className="flex flex-col md:flex-row gap-4 justify-between items-start md:items-center py-4 border-y border-line">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-util text-eyebrow text-ink-soft uppercase text-xs mr-2">
                    Type:
                  </span>
                  {[
                    { label: "All", value: "all" },
                    { label: "News", value: "news" },
                    { label: "Articles", value: "articles" },
                    { label: "Achievements", value: "achievements" },
                  ].map((t) => (
                    <button
                      key={t.value}
                      onClick={() => setSelectedType(t.value)}
                      className={`px-3 py-1 text-xs font-util uppercase tracking-wider border border-line transition-colors ${
                        selectedType === t.value
                          ? "bg-ink text-paper border-ink"
                          : "bg-paper hover:bg-paper-2"
                      }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-util text-eyebrow text-ink-soft uppercase text-xs mr-2">
                    Domain:
                  </span>
                  <select
                    value={selectedDomain}
                    onChange={(e) => setSelectedDomain(e.target.value)}
                    className="border border-line bg-paper text-xs font-util uppercase tracking-wider px-2 py-1 outline-none focus:border-accent"
                  >
                    <option value="all">All Domains</option>
                    {domains.map((d) => (
                      <option key={d.slug} value={d.slug}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Results Display */}
              {loading ? (
                <div className="py-12">
                  <LoadingSkeleton lines={6} />
                </div>
              ) : totalResults > 0 ? (
                <div className="space-y-12">
                  {/* Grouped results count */}
                  <p className="font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                    We found {totalResults} result{totalResults !== 1 && "s"} for &ldquo;{query}&rdquo;
                  </p>

                  {/* Group 1: News */}
                  {hasNews && (
                    <section className="space-y-6">
                      <div className="flex items-center gap-3 border-b border-line pb-2">
                        <h2 className="font-display text-h3 font-medium text-ink">News Updates</h2>
                        <span className="font-util text-xs bg-paper-3 px-2 py-0.5 border border-line text-ink-soft">
                          {filteredNews.length}
                        </span>
                      </div>
                      <div className="card-grid">
                        {filteredNews.map((item) => (
                          <ContentCard key={item.id} variant="news" item={item} />
                        ))}
                      </div>
                    </section>
                  )}

                  {/* Group 2: Articles */}
                  {hasArticles && (
                    <section className="space-y-6">
                      <div className="flex items-center gap-3 border-b border-line pb-2">
                        <h2 className="font-display text-h3 font-medium text-ink">Research Articles</h2>
                        <span className="font-util text-xs bg-paper-3 px-2 py-0.5 border border-line text-ink-soft">
                          {filteredArticles.length}
                        </span>
                      </div>
                      <div className="card-grid">
                        {filteredArticles.map((item) => (
                          <ContentCard key={item.id} variant="article" item={item} />
                        ))}
                      </div>
                    </section>
                  )}

                  {/* Group 3: Achievements */}
                  {hasAchievements && (
                    <section className="space-y-6">
                      <div className="flex items-center gap-3 border-b border-line pb-2">
                        <h2 className="font-display text-h3 font-medium text-ink">Achievements</h2>
                        <span className="font-util text-xs bg-paper-3 px-2 py-0.5 border border-line text-ink-soft">
                          {filteredAchievements.length}
                        </span>
                      </div>
                      <div className="card-grid">
                        {filteredAchievements.map((item) => (
                          <ContentCard key={item.id} variant="achievement" item={item} />
                        ))}
                      </div>
                    </section>
                  )}
                </div>
              ) : (
                <EmptyState
                  actionHref="/search"
                  actionLabel="Reset Search Query"
                  message={`No entries matched query "${query}"`}
                />
              )}
            </>
          )}
        </div>
      )}
    </main>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="kitchen-page py-12 text-center">
          <p className="font-display text-body italic text-ink-soft">Loading search...</p>
        </div>
      }
    >
      <SearchContent />
    </Suspense>
  );
}
