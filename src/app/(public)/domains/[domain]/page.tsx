import * as React from "react";
import { api } from "@/lib/api";
import { Breadcrumb, SectionRail, ContentCard, ErrorState } from "@/components/shared";
import type { NewsItem, Article, Achievement, Domain } from "@/lib/types";

type Params = Promise<{
  domain: string;
}>;

export default async function DomainDetailPage(props: { params: Params }) {
  const { domain: domainSlug } = await props.params;

  let domain: Domain | null = null;
  let newsItems: NewsItem[] = [];
  let articles: Article[] = [];
  let achievements: Achievement[] = [];
  let loadError: string | null = null;

  try {
    domain = await api.domain(domainSlug);
    const [newsRes, articlesRes, magazineRes] = await Promise.allSettled([
      api.newsByDomain(domainSlug),
      api.articlesByDomain(domainSlug),
      api.magazine(),
    ]);

    if (newsRes.status === "fulfilled") newsItems = newsRes.value?.items || [];
    if (articlesRes.status === "fulfilled") articles = articlesRes.value?.items || [];
    if (magazineRes.status === "fulfilled") {
      achievements = ((magazineRes.value?.items || []).filter((a: any) => a.domain?.slug === domainSlug) as any);
    }
  } catch (error: any) {
    loadError = error?.message || `Failed to fetch domain details for '${domainSlug}'.`;
  }

  if (loadError || !domain) {
    return (
      <main className="kitchen-page">
        <Breadcrumb items={[{ label: "Home", href: "/" }, { label: "Domains", href: "/domains" }, { label: "Error" }]} />
        <ErrorState title="Domain Not Found" message={loadError || "The requested academic domain could not be loaded."} />
      </main>
    );
  }

  const hasContent = newsItems.length > 0 || articles.length > 0 || achievements.length > 0;

  return (
    <main className="kitchen-page">
      {/* Header */}
      <header className="space-y-4">
        <Breadcrumb
          items={[
            { label: "Home", href: "/" },
            { label: "Domains", href: "/domains" },
            { label: domain.name },
          ]}
        />
        <div className="flex flex-wrap justify-between items-end gap-4 border-b border-line pb-4">
          <div>
            <h1 className="font-display text-h1 font-semibold leading-tight text-ink">
              {domain.name}
            </h1>
            <p className="font-body text-lede text-ink-soft max-w-xl leading-relaxed mt-2">
              Academic review, publication archive, and student achievements from this domain.
            </p>
          </div>
          {domain.count > 0 && (
            <div className="text-right">
              <span className="font-util text-h2 font-medium text-accent">
                {domain.count}
              </span>
              <p className="font-util text-eyebrow text-ink-soft uppercase tracking-wider mt-1">
                Total entries
              </p>
            </div>
          )}
        </div>
      </header>

      {/* Main grouped sections */}
      {hasContent ? (
        <div className="space-y-12 pt-4">
          {/* News section */}
          {newsItems.length > 0 && (
            <SectionRail
              eyebrow="Updates"
              title="Recent News"
              count={newsItems.length}
              countLabel="News"
              exploreHref={`/news?domain=${domainSlug}`}
              exploreLabel="See all news"
            >
              {newsItems.map((item) => (
                <ContentCard key={item.id} variant="news" item={item} />
              ))}
            </SectionRail>
          )}

          {/* Articles section */}
          {articles.length > 0 && (
            <SectionRail
              eyebrow="Writing"
              title="Research Articles"
              count={articles.length}
              countLabel="Articles"
              exploreHref={`/articles?domain=${domainSlug}`}
              exploreLabel="See all articles"
            >
              {articles.map((item) => (
                <ContentCard key={item.id} variant="article" item={item} />
              ))}
            </SectionRail>
          )}

          {/* Achievements section */}
          {achievements.length > 0 && (
            <SectionRail
              eyebrow="Honors"
              title="Student Achievements"
              count={achievements.length}
              countLabel="Wins"
              exploreHref={`/magazine?department=&type=&year=`}
              exploreLabel="See all magazine achievements"
            >
              {achievements.map((item) => (
                <ContentCard key={item.id} variant="achievement" item={item} />
              ))}
            </SectionRail>
          )}
        </div>
      ) : (
        <div className="py-16 text-center border border-dashed border-line">
          <p className="font-display text-body italic text-ink-soft">
            No entries have been posted under {domain.name} yet.
          </p>
        </div>
      )}
    </main>
  );
}
