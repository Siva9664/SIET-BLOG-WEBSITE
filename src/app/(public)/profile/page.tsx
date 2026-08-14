"use client";

import * as React from "react";
import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Breadcrumb, ContentCard, LoadingSkeleton, EmptyState, Pagination, ErrorState } from "@/components/shared";
import type { User, NewsItem, Article, Achievement } from "@/lib/types";

interface GroupedData {
  news: NewsItem[];
  articles: Article[];
  magazine: Achievement[];
}

type CombinedItem =
  | { variant: "news"; item: NewsItem; date: number }
  | { variant: "article"; item: Article; date: number }
  | { variant: "achievement"; item: Achievement; date: number };

const mapNews = (item: NewsItem): CombinedItem => ({
  variant: "news",
  item,
  date: new Date(item.publishedAt).getTime()
});

const mapArticle = (item: Article): CombinedItem => ({
  variant: "article",
  item,
  date: new Date(item.publishedAt).getTime()
});

const mapAchievement = (item: Achievement): CombinedItem => ({
  variant: "achievement",
  item,
  date: new Date(`${item.year}-01-01T00:00:00.000Z`).getTime()
});

function ProfileContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  const [user, setUser] = useState<User | null>(null);
  const [likes, setLikes] = useState<GroupedData>({ news: [], articles: [], magazine: [] });
  const [bookmarks, setBookmarks] = useState<GroupedData>({ news: [], articles: [], magazine: [] });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const tab = searchParams.get("tab") === "bookmarks" ? "bookmarks" : "likes";
  const pageParam = searchParams.get("page");
  const currentPage = pageParam ? parseInt(pageParam, 10) : 1;
  const itemsPerPage = 6;

  async function loadData() {
    setLoading(true);
    setLoadError(null);
    try {
      const u = await api.getCurrentUser();
      
      if (!u) {
        router.push("/login");
        return;
      }

      setUser(u);

      const [likesData, bookmarksData] = await Promise.all([
        api.myLikes().catch(() => ({ news: [], articles: [], magazine: [] })),
        api.myBookmarks().catch(() => ({ news: [], articles: [], magazine: [] }))
      ]);

      setLikes(likesData);
      setBookmarks(bookmarksData);
    } catch (err: any) {
      if (err?.message && err.message.startsWith("401")) {
        router.push("/login");
        return;
      }
      setLoadError(err?.message || "Failed to load user profile data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [router]);

  if (loading) {
    return (
      <main className="kitchen-page py-12">
        <LoadingSkeleton lines={8} />
      </main>
    );
  }

  if (loadError) {
    return (
      <main className="kitchen-page">
        <Breadcrumb items={[{ label: "Home", href: "/" }, { label: "Reader Profile" }]} />
        <ErrorState title="Profile Error" message={loadError} onRetry={loadData} />
      </main>
    );
  }

  if (!user) return null;

  // Flatten & Sort Likes
  const combinedLikes: CombinedItem[] = [
    ...likes.news.map(mapNews),
    ...likes.articles.map(mapArticle),
    ...likes.magazine.map(mapAchievement)
  ].sort((a, b) => b.date - a.date);

  // Flatten & Sort Bookmarks
  const combinedBookmarks: CombinedItem[] = [
    ...bookmarks.news.map(mapNews),
    ...bookmarks.articles.map(mapArticle),
    ...bookmarks.magazine.map(mapAchievement)
  ].sort((a, b) => b.date - a.date);

  const activeItems = tab === "bookmarks" ? combinedBookmarks : combinedLikes;
  const totalItems = activeItems.length;
  const totalPages = Math.ceil(totalItems / itemsPerPage) || 1;
  const paginatedItems = activeItems.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  const totalLikesCount = combinedLikes.length;
  const totalBookmarksCount = combinedBookmarks.length;

  return (
    <main className="kitchen-page">
      {/* Header */}
      <header className="space-y-4">
        <Breadcrumb items={[{ label: "Home", href: "/" }, { label: "Reader Profile" }]} />
        
        {/* Eyebrow */}
        <p className="font-util text-eyebrow text-accent uppercase tracking-wider">
          Reader Profile
        </p>

        {/* Masthead Header info */}
        <div className="py-6 border-y border-line my-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
              <h1 className="font-display text-h1 font-semibold leading-tight text-ink">
                {user.name}
              </h1>
              <p className="font-util text-eyebrow text-ink-soft uppercase tracking-wider mt-1">
                {user.email}
              </p>
            </div>
            <button
              onClick={async () => {
                await api.logout();
                window.location.href = "/";
              }}
              className="font-util text-eyebrow uppercase tracking-wider text-ink border border-line px-4 py-2 hover:bg-paper-2 transition-colors cursor-pointer"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Tabs navigation */}
      <div className="flex gap-8 border-b border-line mb-8 font-util text-eyebrow uppercase tracking-wider">
        <Link
          href="?tab=likes"
          className={`pb-4 border-b-2 -mb-[1px] transition-colors ${tab === "likes" ? "border-accent text-ink" : "border-transparent text-ink-soft hover:text-ink"}`}
        >
          Likes ({totalLikesCount})
        </Link>
        <Link
          href="?tab=bookmarks"
          className={`pb-4 border-b-2 -mb-[1px] transition-colors ${tab === "bookmarks" ? "border-accent text-ink" : "border-transparent text-ink-soft hover:text-ink"}`}
        >
          Bookmarks ({totalBookmarksCount})
        </Link>
      </div>

      {/* Tab Content: Grid Layout */}
      {totalItems > 0 ? (
        <div className="space-y-12">
          <div className="card-grid">
            {paginatedItems.map(({ variant, item }) => (
              <ContentCard key={item.id} variant={variant as any} item={item as any} />
            ))}
          </div>

          {/* Client-side Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-center pt-6">
              <Pagination page={currentPage} pages={totalPages} basePath={`/profile?tab=${tab}`} />
            </div>
          )}
        </div>
      ) : (
        <EmptyState
          actionHref="/"
          actionLabel="Explore Articles"
          message={
            tab === "bookmarks"
              ? "You haven't bookmarked anything yet."
              : "You haven't liked anything yet."
          }
        />
      )}
    </main>
  );
}

export default function ProfilePage() {
  return (
    <Suspense
      fallback={
        <div className="kitchen-page py-12 text-center">
          <p className="font-display text-body italic text-ink-soft">Loading profile...</p>
        </div>
      }
    >
      <ProfileContent />
    </Suspense>
  );
}
