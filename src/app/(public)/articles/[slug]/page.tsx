import * as React from "react";
import Image from "next/image";
import { api } from "@/lib/api";
import {
  Breadcrumb,
  SectionRail,
  ContentCard,
  TagChip,
  AuthorCard,
  LikeButton,
  BookmarkButton,
  ShareButton,
  ErrorState,
} from "@/components/shared";
import type { Article } from "@/lib/types";

type Params = Promise<{
  slug: string;
}>;

export default async function ArticleDetailPage(props: { params: Params }) {
  const { slug } = await props.params;

  let item: Article | null = null;
  let related: Article[] = [];
  let loadError: string | null = null;

  try {
    item = await api.articleBySlug(slug);
    if (item && item.domain?.slug) {
      try {
        const res = await api.articlesByDomain(item.domain.slug);
        related = (res.items || []).filter((r) => r.slug !== slug).slice(0, 4);
      } catch {
        related = [];
      }
    }
  } catch (error: any) {
    loadError = error?.message || `Failed to load article '${slug}' from server.`;
  }

  if (loadError || !item) {
    return (
      <main className="kitchen-page">
        <Breadcrumb items={[{ label: "Home", href: "/" }, { label: "Articles", href: "/articles" }, { label: "Error" }]} />
        <ErrorState title="Article Not Found" message={loadError || "The requested article could not be loaded."} />
      </main>
    );
  }

  const dateString = new Date(item.publishedAt).toLocaleDateString("en", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  });

  return (
    <main className="kitchen-page">
      {/* Breadcrumbs Header */}
      <header className="space-y-4">
        <Breadcrumb
          items={[
            { label: "Home", href: "/" },
            { label: "Articles", href: "/articles" },
            { label: item.title },
          ]}
        />
        <h1 className="font-display text-h1 font-semibold leading-tight text-ink">
          {item.title}
        </h1>

        {/* Metadata section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 py-4 border-y border-line">
          {/* Author metadata */}
          <AuthorCard author={item.author} />

          {/* Reading specs */}
          <div className="flex items-center gap-4 text-ink-soft font-util text-eyebrow uppercase tracking-wider md:text-right">
            <span>{item.domain?.name ?? "General"}</span>
            <span className="text-line">·</span>
            <span>{dateString}</span>
            <span className="text-line">·</span>
            <span className="text-accent font-medium">{item.readingMinutes} MIN READ</span>
          </div>
        </div>
      </header>

      {/* Hero Cover Image */}
      {item.cover && (
        <div className="relative aspect-video w-full overflow-hidden border border-line bg-paper-2">
          <Image
            src={item.cover}
            alt={item.title}
            fill
            priority
            sizes="100vw"
            className="object-cover grayscale contrast-110"
          />
        </div>
      )}

      {/* Rich-Text Body Block */}
      <article
        className="font-body text-body text-ink space-y-6 max-w-2xl leading-relaxed prose prose-stone"
        dangerouslySetInnerHTML={{ __html: item.body }}
      />

      {/* Tags Row */}
      {item.tags && item.tags.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-6 border-t border-line">
          {item.tags.map((tag) => (
            <TagChip key={tag.slug} label={tag.name} href={`/articles?domain=${item?.domain?.slug || ""}`} />
          ))}
        </div>
      )}

      {/* Social Interactions Action Bar */}
      <div className="flex items-center gap-4 py-4 border-y border-line">
        <LikeButton type="articles" slug={item.slug} count={item.likes} />
        <BookmarkButton type="articles" slug={item.slug} bookmarked={item.bookmarked} />
        <ShareButton title={item.title} url={`/articles/${item.slug}`} />
      </div>

      {/* Related Articles Rail */}
      {related.length > 0 && (
        <div className="pt-8 border-t border-line">
          <SectionRail
            eyebrow="More from this topic"
            title="Related Articles"
            count={related.length}
            countLabel="Articles"
            exploreHref="/articles"
            exploreLabel="Explore all articles"
          >
            {related.map((r) => (
              <ContentCard key={r.id} variant="article" item={r} />
            ))}
          </SectionRail>
        </div>
      )}
    </main>
  );
}
