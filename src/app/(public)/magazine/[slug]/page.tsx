import * as React from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { Breadcrumb, LikeButton, BookmarkButton, ShareButton } from "@/components/shared";
import { MagazineViewer } from "@/components/magazine/MagazineViewer";
import type { MagazineIssue } from "@/lib/types";

type Params = Promise<{
  slug: string;
}>;

export default async function MagazineDetailPage(props: { params: Params }) {
  const { slug } = await props.params;

  let issue: MagazineIssue | null = null;

  try {
    issue = await api.magBySlug(slug);
  } catch (error) {
    console.error(`Failed to load magazine issue for slug '${slug}':`, error);
  }

  if (!issue) {
    notFound();
  }

  return (
    <main className="kitchen-page space-y-8">
      {/* Header & Breadcrumb */}
      <header className="space-y-4 border-b border-line pb-6">
        <Breadcrumb
          items={[
            { label: "Home", href: "/" },
            { label: "Magazine", href: "/magazine" },
            { label: issue.title },
          ]}
        />

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 font-util text-[10px] uppercase tracking-wider text-ink-soft">
            <span className="text-accent font-semibold">{issue.type} Issue</span>
            <span>·</span>
            <span>
              {new Date(issue.issueDate || Date.now()).toLocaleDateString("en-US", {
                month: "long",
                day: "numeric",
                year: "numeric",
              })}
            </span>
            {(issue.pageCount || 0) > 0 && (
              <>
                <span>·</span>
                <span>{issue.pageCount} Pages</span>
              </>
            )}
          </div>

          {issue.pdfUrl && (
            <a
              href={issue.pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="font-util text-eyebrow uppercase tracking-wider text-ink hover:text-accent border border-line px-3 py-1 bg-paper hover:bg-paper-3 transition-colors"
            >
              Original PDF Direct ↗
            </a>
          )}
        </div>

        <h1 className="font-display text-h1 font-semibold leading-tight text-ink">
          {issue.title}
        </h1>

        {issue.description && (
          <p className="font-body text-body text-ink-soft max-w-3xl leading-relaxed">
            {issue.description}
          </p>
        )}
      </header>

      {/* Interactive Page Viewer */}
      <section>
        <MagazineViewer issue={issue} />
      </section>

      {/* Social Interactions Action Bar */}
      <div className="flex items-center gap-4 py-4 border-y border-line my-8">
        <LikeButton type="magazine" slug={issue.slug} count={issue.likes || 0} />
        <BookmarkButton type="magazine" slug={issue.slug} bookmarked={issue.bookmarked} />
        <ShareButton title={issue.title} url={`/magazine/${issue.slug}`} />
      </div>
    </main>
  );
}
