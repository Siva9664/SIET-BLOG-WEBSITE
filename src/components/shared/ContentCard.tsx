"use client";

import Image from "next/image";
import Link from "next/link";
import type { Achievement, Article, NewsItem } from "@/lib/types";
import { BookmarkButton, LikeButton, ShareButton } from "./ActionButtons";
import { TagChip } from "./TagChip";

type ContentCardProps =
  | { variant: "news"; item: NewsItem }
  | { variant: "article"; item: Article }
  | { variant: "achievement"; item: Achievement };

function formatDate(value?: string) {
  if (!value) return "";
  return new Intl.DateTimeFormat("en", { month: "short", day: "2-digit", year: "numeric" }).format(
    new Date(value),
  );
}

export function ContentCard(props: ContentCardProps) {
  const { variant, item } = props;
  const href =
    variant === "news"
      ? `/news/${item.slug}`
      : variant === "article"
        ? `/articles/${item.slug}`
        : `/magazine/${item.slug}`;
  const image =
    variant === "news" ? item.image : variant === "article" ? item.cover : item.gallery?.[0];
  const excerpt =
    variant === "news" ? item.aiSummary : variant === "article" ? item.excerpt : item.description;
  const date = variant === "achievement" ? `${item.year}` : formatDate(item.publishedAt);
  const footer =
    variant === "news"
      ? `${item.sourceName ?? "SIET Desk"} · ${item.likes ?? 0} likes`
      : variant === "article"
        ? `${item.author?.name ?? "Author"} · ${item.readingMinutes ?? 5} min read`
        : `${item.student?.name ?? "Student"} · ${item.department ?? ""}`;

  const isMultiSource = variant === "news" && (item.coverageCount ?? 0) > 1;
  const coverageList = variant === "news" ? item.coverage || [] : [];

  return (
    <article className="content-card reveal group flex flex-col justify-between">
      <div>
        <Link className="content-card-media relative block" href={href}>
          {image ? (
            <Image
              src={image}
              alt={item.title}
              fill
              unoptimized
              sizes="(max-width: 768px) 100vw, (max-width: 1200px) 33vw, 25vw"
              className="object-cover transition-transform duration-700 ease-out group-hover:scale-105"
            />
          ) : (
            <div className="ruled-placeholder" aria-hidden="true">
              <span>No image</span>
            </div>
          )}
        </Link>
        <div className="content-card-body">
          <div className="flex items-center justify-between gap-2">
            <p className="eyebrow flex items-center flex-wrap gap-1.5">
              <span>{item.domain?.name ?? "General"} · {date}</span>
              {isMultiSource && (
                <span className="inline-flex items-center gap-1 rounded bg-amber-500/20 text-amber-800 dark:text-amber-200 border border-amber-500/30 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider">
                  ⚡ {item.coverageCount} SOURCES
                </span>
              )}
            </p>
          </div>
          <h3 className="mt-1">
            <Link href={href}>{item.title}</Link>
          </h3>
          <p className="line-clamp-3 mt-1.5 text-ink-soft">{excerpt}</p>
        </div>

        {/* Tags Row */}
        <div className="content-card-tags">
          {variant === "achievement" ? (
            <TagChip label={item.type} />
          ) : (
            (item.tags || []).slice(0, 2).map((tag, idx) => {
              const label = typeof tag === "string" ? tag : tag.name || tag.slug;
              return <TagChip key={idx} label={label} />;
            })
          )}
        </div>

        {/* Multi-Source Outlet Links Row */}
        {variant === "news" && (
          <div className="px-4 pb-2 pt-1 border-t border-line/50 space-y-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-ink-soft block">
              {coverageList.length > 1 ? "Verified Media Outlets:" : "Source Outlet:"}
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              {coverageList.length > 0 ? (
                coverageList.map((cov) => {
                  const sName = cov.sourceName || cov.source_name || "Source";
                  const covUrl = cov.url || cov.source_url || item.sourceUrl;
                  return (
                    <a
                      key={cov.id || `${sName}-${covUrl}`}
                      href={covUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 border border-line bg-paper-2 hover:bg-amber-500/10 hover:border-amber-500/50 hover:text-amber-600 dark:hover:text-amber-300 text-[11px] px-2 py-0.5 rounded transition-colors text-ink font-medium"
                      title={`Read coverage on ${sName}: ${cov.title}`}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <span>{sName}</span>
                      <span className="text-[9px] opacity-70">↗</span>
                    </a>
                  );
                })
              ) : item.sourceUrl ? (
                <a
                  href={item.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 border border-line bg-paper-2 hover:bg-accent/10 hover:border-accent hover:text-accent text-[11px] px-2 py-0.5 rounded transition-colors text-ink font-medium"
                  title={`Read full article on ${item.sourceName}`}
                  onClick={(e) => e.stopPropagation()}
                >
                  <span>{item.sourceName || "Original Source"}</span>
                  <span className="text-[9px] opacity-70">↗</span>
                </a>
              ) : (
                <span className="text-[11px] text-ink-soft">{item.sourceName || "SIET Tech Desk"}</span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Card Footer */}
      <footer className="content-card-footer">
        <span>
          {variant === "news"
            ? `${item.likes ?? 0} likes`
            : footer}
        </span>
        <div>
          {"likes" in item ? (
            <LikeButton
              type={variant === "news" ? "news" : variant === "article" ? "articles" : "magazine"}
              slug={item.slug}
              count={item.likes}
            />
          ) : null}
          {"bookmarked" in item ? (
            <BookmarkButton
              type={variant === "news" ? "news" : variant === "article" ? "articles" : "magazine"}
              slug={item.slug}
              bookmarked={item.bookmarked}
            />
          ) : null}
          <ShareButton title={item.title} url={href} />
        </div>
      </footer>
    </article>
  );
}
