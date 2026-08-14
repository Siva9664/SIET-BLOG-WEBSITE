import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { F1IntroHero } from "@/components/signature/F1IntroHero";
import { FeatureMosaic, type MosaicItem } from "@/components/signature/FeatureMosaic";
import { ContentCard, SectionRail, ErrorState } from "@/components/shared";
import type { Achievement, Article, Domain, NewsItem } from "@/lib/types";

function toMosaicItem(item: NewsItem): MosaicItem {
  return {
    id: item.id,
    title: item.title,
    image: item.image,
    name: item.sourceName,
    role: item.domain?.name || "News",
    href: `/news/${item.slug}`,
  };
}

export default async function HomePage() {
  let homeData: any = {};
  let loadError: string | null = null;
  
  try {
    homeData = await api.home();
  } catch (error: any) {
    loadError = error?.message || "Failed to fetch homepage portal data from backend API.";
  }

  const realFeatured: NewsItem[] = homeData.featured ?? [];
  const realTrending: NewsItem[] = homeData.trending ?? [];
  const realArticles: Article[] = homeData.latestArticles ?? [];
  const realAchievements: Achievement[] = homeData.latestAchievements ?? [];

  const featured = realFeatured.length > 0 ? toMosaicItem(realFeatured[0]) : null;
  const tiles = realFeatured.length > 1 ? realFeatured.slice(1).map(toMosaicItem) : [];
  const news = realTrending.length ? realTrending : realFeatured;
  const newsCount = news.length;
  const articles = realArticles;
  const achievements = realAchievements;

  return (
    <>
      <F1IntroHero />
      <main className="kitchen-page">
        {/* 1. Masthead */}
        <header className="flex flex-col gap-3 pt-6 reveal">
          <h1 className="font-display text-masthead font-semibold leading-[0.9] text-ink tracking-tight">
            SIET News
          </h1>
          <p className="font-util text-eyebrow text-ink-soft tracking-[0.14em] uppercase">
            AI Research Lab · Sri Shakthi Institute of Engineering and Technology
          </p>
          <p className="font-body text-lede text-ink max-w-xl mt-2 leading-relaxed">
            AI news, student writing, research papers, and active achievements of our department.
          </p>
        </header>

        {loadError ? (
          <div className="pt-8">
            <ErrorState title="Portal Offline" message={loadError} />
          </div>
        ) : (
          <>
            {/* 2. FeatureMosaic hero (if featured item exists) */}
            {featured && <FeatureMosaic featured={featured} tiles={tiles} />}

            {/* 3. Section 1: Tech & Lab News */}
            {news.length > 0 && (
              <SectionRail
                eyebrow="Section 01 / Tech & Lab News"
                title="Latest News Updates"
                count={newsCount}
                countLabel="Articles"
                exploreHref="/news"
                exploreLabel="Explore all news"
              >
                {news.map((item) => (
                  <ContentCard key={item.id} variant="news" item={item} />
                ))}
              </SectionRail>
            )}

            {/* 4. Section 2: Student Writing */}
            {articles.length > 0 && (
              <SectionRail
                eyebrow="Section 02 / Student Writing"
                title="Research Articles & Notes"
                count={articles.length}
                countLabel="Papers"
                exploreHref="/articles"
                exploreLabel="Explore all articles"
              >
                {articles.map((item) => (
                  <ContentCard key={item.id} variant="article" item={item} />
                ))}
              </SectionRail>
            )}

            {/* 5. Section 3: Student Achievements */}
            {achievements.length > 0 && (
              <SectionRail
                eyebrow="Section 03 / Student Wins"
                title="Achievements & Honors"
                count={achievements.length}
                countLabel="Records"
                exploreHref="/magazine"
                exploreLabel="View full magazine archive"
              >
                {achievements.map((item) => (
                  <ContentCard key={item.id} variant="achievement" item={item} />
                ))}
              </SectionRail>
            )}
          </>
        )}
      </main>
    </>
  );
}
