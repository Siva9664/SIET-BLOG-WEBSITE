import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { api } from "@/lib/api";
import {
  Breadcrumb,
  SectionRail,
  ContentCard,
  TagChip,
  LikeButton,
  BookmarkButton,
  ShareButton,
} from "@/components/shared";
import type { NewsItem, CoverageEntry, DetailedSection } from "@/lib/types";

type Params = Promise<{
  slug: string;
}>;

export default async function NewsDetailPage(props: { params: Params }) {
  const { slug } = await props.params;

  let item: any;
  let related: NewsItem[] = [];
  let isFallback = false;

  try {
    item = await api.newsBySlug(slug);
  } catch (error) {
    console.warn(`News detail API for slug '${slug}' offline or not found.`, error);
    isFallback = true;
    item = {
      id: "fallback-1",
      slug: slug,
      title: slug.split("-").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" "),
      content: "Detailed technology article overview.",
      aiSummary: "AI summary of key engineering developments across sources.",
      simpleExplanation: "Simple 2-4 sentence plain language explanation of recent engineering developments.",
      detailedSections: [
        {
          heading: "Overview & Key Announcement",
          paragraphs: ["Detailed technical analysis of recent progress across multiple reporting outlets."]
        }
      ],
      contentDepth: "summary_only",
      keyPoints: ["• Core performance improvements", "• Architectural changes", "• Industry standards shift"],
      technicalDetails: "System design patterns and benchmarking results.",
      whyItMatters: "Enables developers to leverage optimized runtime patterns.",
      studentRelevance: "For SIET students: Provides practical reference for senior design projects.",
      department: "ai-ml",
      subcategory: "General",
      verificationStatus: "single_source",
      coverageCount: 1,
      coverage: [
        {
          id: "cov-1",
          sourceName: "Tech News Outlet",
          title: slug.split("-").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" "),
          url: "https://techcrunch.com",
          publishedAt: new Date().toISOString(),
          isPrimary: true,
        }
      ],
      sourceUrl: "https://techcrunch.com",
      sourceName: "Tech News Source",
      author: "Engineering Desk",
      publishedAt: new Date().toISOString(),
      likes: 12,
    };
  }

  try {
    const res = await api.newsByDomain(item.department || "ai-ml");
    related = (res.items || []).filter((r: any) => r.slug !== slug).slice(0, 4);
  } catch (error) {
    console.warn("Related news API call failed.", error);
  }

  const dateString = new Date(item.publishedAt).toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  });

  const isConfirmed = item.verificationStatus === "confirmed" || (item.coverageCount && item.coverageCount >= 2);
  const coverageList: CoverageEntry[] = item.coverage && item.coverage.length > 0
    ? item.coverage
    : [
        {
          id: "1",
          sourceName: item.sourceName || "Primary Outlet",
          title: item.title,
          url: item.sourceUrl || "#",
          publishedAt: item.publishedAt,
          isPrimary: true,
        }
      ];

  const detailedSections: DetailedSection[] = item.detailedSections && item.detailedSections.length > 0
    ? item.detailedSections
    : [
        {
          heading: "Detailed Breakdown",
          paragraphs: [item.detailedSummary || item.content || "Overview text."]
        }
      ];

  const isSummaryOnly = item.contentDepth === "summary_only";

  return (
    <main className="kitchen-page max-w-4xl mx-auto px-4 py-8 space-y-8">
      {isFallback && (
        <div className="bg-amber-500 text-black px-4 py-2 text-center text-sm font-semibold rounded">
          ⚠ Showing sample content — live article data unavailable
        </div>
      )}

      {/* Header & Verification Metadata */}
      <header className="space-y-4 reveal">
        <Breadcrumb
          items={[
            { label: "Home", href: "/" },
            { label: "SIET News", href: "/news" },
            { label: (item.department || "AI/ML").toUpperCase(), href: `/news?department=${item.department || "ai-ml"}` },
            { label: item.title },
          ]}
        />

        <div className="flex flex-wrap items-center gap-3 pt-2">
          <TagChip label={(item.department || "AI-ML").toUpperCase()} href={`/news?department=${item.department || "ai-ml"}`} active />
          {item.subcategory && item.subcategory !== "General" && (
            <TagChip label={item.subcategory} />
          )}

          {/* Verification Badge */}
          {isConfirmed ? (
            <span className="px-3 py-1 bg-emerald-500/10 border border-emerald-500/40 text-emerald-700 dark:text-emerald-400 text-xs font-mono rounded-full font-bold flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              ✓ Confirmed by {item.coverageCount || coverageList.length} sources
            </span>
          ) : (
            <span className="px-3 py-1 bg-line/60 border border-line text-ink-soft text-xs font-mono rounded-full">
              Reported by {item.sourceName || "Primary Source"}
            </span>
          )}
        </div>

        <h1 className="font-display text-h1 font-semibold leading-tight text-ink">
          {item.title}
        </h1>

        <div className="flex flex-wrap items-center justify-between text-ink-soft font-util text-eyebrow border-y border-line py-3">
          <div className="flex items-center gap-3">
            <span>Primary: <strong className="text-ink">{item.sourceName || "Original Publisher"}</strong></span>
            <span>•</span>
            <span>By: <strong className="text-ink">{item.author || "Tech Desk"}</strong></span>
          </div>
          <div className="flex items-center gap-3">
            <span>Published: {dateString}</span>
            <span>•</span>
            <span className="text-accent">
              {isSummaryOnly ? "1 min summary" : "~3 min read"}
            </span>
          </div>
        </div>
      </header>

      {/* Hero Image */}
      {item.image && (
        <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-line bg-line/20 shadow-sm reveal">
          <Image
            src={item.image}
            alt={item.title}
            fill
            priority
            unoptimized
            sizes="(max-width: 1200px) 100vw, 1200px"
            className="object-cover"
          />
        </div>
      )}

      {/* 1. SIMPLE EXPLANATION (2-4 lines plain language dek) */}
      <div className="rounded-lg border border-line bg-line/30 p-6 space-y-2 reveal">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-accent font-util text-eyebrow tracking-widest uppercase font-semibold">
            <span className="h-2 w-2 rounded-full bg-accent animate-pulse" />
            Simple Explanation
          </div>
          <span className="font-util text-eyebrow text-ink-soft">Plain Language • No Jargon</span>
        </div>
        <p className="text-lg text-ink font-body leading-relaxed italic">
          "{item.simpleExplanation || item.contentSummary || item.aiSummary}"
        </p>
      </div>

      {/* 2. DETAILED EXPLANATION — DYNAMIC SUBHEADINGS */}
      <section className="space-y-8 pt-2 reveal">
        <div className="flex items-center justify-between border-b border-line pb-3">
          <h2 className="font-display text-h2 font-semibold text-ink flex items-center gap-2">
            Detailed Explanation
          </h2>
          {isSummaryOnly && (
            <span className="font-util text-eyebrow text-amber-700 dark:text-amber-400 bg-amber-500/10 border border-amber-500/30 px-3 py-1 rounded-full">
              ⚡ Limited source detail available — showing publisher summary
            </span>
          )}
        </div>

        {/* Render dynamic sections mapped over detailed_sections */}
        <div className="space-y-8">
          {detailedSections.map((sec: DetailedSection, idx: number) => (
            <div key={idx} className="space-y-3">
              <h3 className="font-display text-h3 font-medium text-ink flex items-center gap-2">
                <span className="text-accent font-util text-eyebrow font-semibold">{idx + 1}.</span>
                {sec.heading}
              </h3>
              <div className="text-ink text-body leading-relaxed space-y-4 pl-6 border-l-2 border-line">
                {sec.paragraphs && sec.paragraphs.length > 0 ? (
                  sec.paragraphs.map((p: string, pIdx: number) => (
                    <p key={pIdx}>{p}</p>
                  ))
                ) : (
                  <p>{item.content}</p>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Key Technical Takeaways */}
        {item.keyPoints && item.keyPoints.length > 0 && (
          <div className="rounded-lg border border-line bg-line/20 p-6 space-y-3 mt-8">
            <h3 className="font-util text-eyebrow font-bold uppercase tracking-wider text-accent flex items-center gap-2">
              <span>⚡</span> Key Technical Takeaways
            </h3>
            <ul className="space-y-2 text-ink text-sm font-body">
              {item.keyPoints.map((point: string, idx: number) => (
                <li key={idx} className="flex items-start gap-2.5">
                  <span className="text-accent font-bold">›</span>
                  <span>{point.replace(/^•\s*/, '')}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Technical Architecture & Impact */}
        {item.technicalDetails && (
          <div className="space-y-3 pt-4">
            <h3 className="font-display text-h3 font-medium text-ink flex items-center gap-2">
              Technical Architecture & Impact
            </h3>
            <p className="text-ink text-body leading-relaxed font-body">
              {item.technicalDetails}
            </p>
          </div>
        )}

        {/* Why It Matters */}
        {item.whyItMatters && (
          <div className="space-y-3 pt-4">
            <h3 className="font-display text-h3 font-medium text-ink flex items-center gap-2">
              Why This Matters for Engineers
            </h3>
            <p className="text-ink text-body leading-relaxed font-body">
              {item.whyItMatters}
            </p>
          </div>
        )}

        {/* Student Relevance Banner */}
        {item.studentRelevance && (
          <div className="rounded-lg border border-accent/30 bg-accent/5 p-6 space-y-2">
            <div className="flex items-center gap-2 text-accent font-util text-eyebrow uppercase tracking-widest font-semibold">
              🎓 SIET Engineering Student Relevance
            </div>
            <p className="text-sm text-ink leading-relaxed font-body">
              {item.studentRelevance}
            </p>
          </div>
        )}

        {/* Tags */}
        {item.tags && item.tags.length > 0 && (
          <div className="space-y-3 pt-4">
            <h4 className="font-util text-eyebrow uppercase tracking-wider text-ink-soft">Related Technologies</h4>
            <div className="flex flex-wrap gap-2">
              {item.tags.map((tag: any, idx: number) => {
                const tagName = typeof tag === "string" ? tag : tag.name || tag.slug;
                return <TagChip key={idx} label={tagName} href={`/news?q=${encodeURIComponent(tagName)}`} />;
              })}
            </div>
          </div>
        )}
      </section>

      {/* Coverage Section — Multi-source Reporting Breakdown */}
      <section className="rounded-lg border border-line bg-line/20 p-6 space-y-4 reveal">
        <div className="flex items-center justify-between border-b border-line pb-3">
          <div className="space-y-1">
            <h3 className="font-display text-h3 font-medium text-ink flex items-center gap-2">
              <span>🌐</span> Multi-Source Coverage
            </h3>
            <p className="font-util text-eyebrow text-ink-soft">
              Reported by {coverageList.length} independent outlet{coverageList.length > 1 ? "s" : ""}
            </p>
          </div>
          {isConfirmed && (
            <span className="px-3 py-1 bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-400 font-util text-eyebrow rounded-full font-bold">
              ✓ Verified Story
            </span>
          )}
        </div>

        <div className="divide-y divide-line">
          {coverageList.map((cov: CoverageEntry, idx: number) => (
            <div key={idx} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-line/40 px-3 rounded transition-colors">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-util text-eyebrow font-bold text-accent">{cov.sourceName}</span>
                  {cov.isPrimary && (
                    <span className="px-2 py-0.5 bg-accent/10 border border-accent/30 text-accent text-[10px] font-util rounded uppercase">
                      Primary
                    </span>
                  )}
                </div>
                <h4 className="text-sm font-semibold text-ink">
                  "{cov.title}"
                </h4>
                <p className="font-util text-eyebrow text-ink-soft">
                  {new Date(cov.publishedAt).toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" })}
                </p>
              </div>

              {cov.url && (
                <a
                  href={cov.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 px-3 py-1.5 bg-line/60 hover:bg-line text-accent border border-line text-xs font-util rounded transition-colors inline-flex items-center gap-1.5 self-start sm:self-center"
                >
                  Read on {cov.sourceName} ↗
                </a>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* External Original Source Attribution Button */}
      {item.sourceUrl && (
        <div className="pt-4 border-t border-line flex items-center justify-between reveal">
          <span className="font-util text-eyebrow text-ink-soft">Canonical Article Source</span>
          <a
            href={item.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-accent/10 hover:bg-accent/20 text-accent border border-accent/30 text-xs font-util rounded transition-colors inline-flex items-center gap-2 font-bold"
          >
            Read Original Article on {item.sourceName || "Publisher"} ↗
          </a>
        </div>
      )}

      {/* Social Interactions */}
      <div className="flex items-center gap-4 py-4 border-y border-line reveal">
        <LikeButton type="news" slug={item.slug} count={item.likes || 0} />
        <BookmarkButton type="news" slug={item.slug} bookmarked={item.bookmarked} />
        <ShareButton title={item.title} url={`/news/${item.slug}`} />
      </div>

      {/* Related News Rail */}
      {related.length > 0 && (
        <div className="pt-8 border-t border-line reveal">
          <SectionRail
            eyebrow="Related updates"
            title="Recommended Reading"
            count={related.length}
            countLabel="Updates"
            exploreHref="/news"
            exploreLabel="Explore all news"
          >
            {related.map((r: any) => (
              <ContentCard key={r.id} variant="news" item={r} />
            ))}
          </SectionRail>
        </div>
      )}
    </main>
  );
}
