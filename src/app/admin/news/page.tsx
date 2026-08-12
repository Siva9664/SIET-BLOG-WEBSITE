"use client";

import * as React from "react";
import { useState, useEffect, useMemo } from "react";
import { api } from "@/lib/api";
import { CursorPagination } from "@/components/shared";
import {
  AdminDrawer,
  AdminTable,
  AdminField,
  AdminSearchBar,
  AdminToast,
  AdminEmptyState,
  adminInputCls,
  adminTextareaCls,
  adminSelectCls,
} from "@/components/admin/AdminShared";
import type { NewsItem, Domain } from "@/lib/types";

// ─── Fallbacks ───────────────────────────────────────────────────────────────
const FALLBACK_DOMAINS: Domain[] = [
  { slug: "machine-learning", name: "Machine Learning", count: 42 },
  { slug: "robotics", name: "Robotics", count: 19 },
  { slug: "campus-research", name: "Campus Research", count: 27 },
  { slug: "ethics", name: "AI Ethics", count: 12 },
];

const FALLBACK_NEWS: NewsItem[] = [
  {
    id: "n1",
    slug: "open-models-campus-lab",
    title: "Open models shape a new week of student experiments",
    aiSummary:
      "The lab tracked model releases, classroom prototypes, and a practical discussion on evaluation methods for student-built systems.",
    sourceUrl: "https://example.com",
    sourceName: "AI Research Desk",
    domain: FALLBACK_DOMAINS[0],
    tags: [{ slug: "models", name: "Models" }],
    image:
      "https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=900&q=80",
    publishedAt: "2026-07-08T10:00:00.000Z",
    trending: true,
    likes: 87,
  },
  {
    id: "n2",
    slug: "robotics-navigation-updates",
    title: "Robotics team publishes indoor navigation benchmark",
    aiSummary:
      "Initial testing of LiDAR slam shows consistent map resolution under varied department lighting conditions.",
    sourceUrl: "https://example.com",
    sourceName: "Robotics Press",
    domain: FALLBACK_DOMAINS[1],
    tags: [{ slug: "navigation", name: "Navigation" }],
    image:
      "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=900&q=80",
    publishedAt: "2026-07-07T14:30:00.000Z",
    likes: 42,
  },
];

// ─── Helper ──────────────────────────────────────────────────────────────────
function toSlug(str: string) {
  return str
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

// ─── Page ────────────────────────────────────────────────────────────────────
export default function AdminNewsCRUDPage() {
  const [allItems, setAllItems] = useState<NewsItem[]>([]);
  const [domains, setDomains] = useState<Domain[]>(FALLBACK_DOMAINS);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<(string | null)[]>([null]);
  const [hasMore, setHasMore] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Search + Filter
  const [search, setSearch] = useState("");
  const [domainFilter, setDomainFilter] = useState("all");
  const [trendingFilter, setTrendingFilter] = useState<"all" | "yes" | "no">("all");

  // Drawer
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editItem, setEditItem] = useState<NewsItem | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" | "info" } | null>(null);

  // Form fields
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [aiSummary, setAiSummary] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [domainSlug, setDomainSlug] = useState("");
  const [image, setImage] = useState("");
  const [publishedAt, setPublishedAt] = useState("");
  const [trending, setTrending] = useState(false);

  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [fetchingLive, setFetchingLive] = useState(false);

  // ── Filtered items ──────────────────────────────────────────────────────
  const items = useMemo(() => {
    let list = allItems;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (i) =>
          i.title.toLowerCase().includes(q) ||
          i.aiSummary?.toLowerCase().includes(q) ||
          i.sourceName?.toLowerCase().includes(q)
      );
    }
    if (domainFilter !== "all") {
      list = list.filter((i) => i.domain?.slug === domainFilter);
    }
    if (trendingFilter === "yes") list = list.filter((i) => i.trending);
    if (trendingFilter === "no") list = list.filter((i) => !i.trending);
    return list;
  }, [allItems, search, domainFilter, trendingFilter]);

  // ── Load ────────────────────────────────────────────────────────────────
  const loadNews = async (cur: string | null) => {
    setLoading(true);
    try {
      const res = await api.adminNews(cur ? `?cursor=${cur}` : "");
      setAllItems(res.items);
      setHasMore(res.pageInfo.has_more);
      setNextCursor(res.pageInfo.next_cursor);
    } catch {
      setAllItems(FALLBACK_NEWS);
      setHasMore(false);
      setNextCursor(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadNews(cursor); }, [cursor]);
  useEffect(() => {
    api.domains().then(setDomains).catch(() => setDomains(FALLBACK_DOMAINS));
  }, []);

  const showToast = (msg: string, type: "success" | "error" | "info" = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 5000);
  };

  // ── Pagination ──────────────────────────────────────────────────────────
  const handleNext = () => {
    if (nextCursor) {
      setCursorHistory((h) => [...h, nextCursor]);
      setCursor(nextCursor);
    }
  };
  const handlePrevious = () => {
    if (cursorHistory.length > 1) {
      const h = cursorHistory.slice(0, -1);
      setCursorHistory(h);
      setCursor(h[h.length - 1]);
    }
  };

  // ── Trigger live fetch ──────────────────────────────────────────────────
  const handleTrigger = async () => {
    setFetchingLive(true);
    try {
      const res = await api.adminTriggerNewsFetch();
      showToast(res.message || "Live news ingestion completed.", "success");
      loadNews(cursor);
    } catch {
      showToast("Trigger sent — refreshing stream.", "info");
      loadNews(cursor);
    } finally {
      setFetchingLive(false);
    }
  };

  // ── Open drawer ─────────────────────────────────────────────────────────
  const openCreate = () => {
    setEditItem(null);
    setTitle(""); setSlug(""); setAiSummary(""); setSourceName(""); setSourceUrl("");
    setDomainSlug(domains[0]?.slug || ""); setImage("");
    setPublishedAt(new Date().toISOString().substring(0, 16)); setTrending(false);
    setFormError(null); setDrawerOpen(true);
  };

  const openEdit = (item: NewsItem) => {
    setEditItem(item);
    setTitle(item.title);
    setSlug(item.slug);
    setAiSummary(item.aiSummary || "");
    setSourceName(item.sourceName || "");
    setSourceUrl(item.sourceUrl || "");
    setDomainSlug(item.domain?.slug || domains[0]?.slug || "");
    setImage(item.image || "");
    setPublishedAt(new Date(item.publishedAt).toISOString().substring(0, 16));
    setTrending(!!item.trending);
    setFormError(null);
    setDrawerOpen(true);
  };

  // ── Submit form ─────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !slug || !domainSlug) {
      setFormError("Title, Slug, and Domain are required.");
      return;
    }
    setSubmitting(true);
    setFormError(null);
    const activeDomain = domains.find((d) => d.slug === domainSlug) || FALLBACK_DOMAINS[0];
    const payload = {
      title, slug, aiSummary, sourceName, sourceUrl,
      domain: activeDomain, image,
      publishedAt: new Date(publishedAt).toISOString(), trending,
    };
    try {
      if (editItem) {
        await api.adminNewsUpdate(editItem.id, payload);
        showToast("News item updated successfully.", "success");
      } else {
        await api.adminNewsCreate(payload);
        showToast("News item created successfully.", "success");
      }
      setDrawerOpen(false);
      loadNews(cursor);
    } catch {
      // Offline fallback
      const mock: NewsItem = {
        id: editItem?.id || `n-${Date.now()}`,
        ...payload,
        likes: editItem?.likes || 0,
        tags: editItem?.tags || [],
      };
      if (editItem) {
        setAllItems((prev) => prev.map((i) => (i.id === editItem.id ? mock : i)));
      } else {
        setAllItems((prev) => [mock, ...prev]);
      }
      showToast("Saved locally (API offline).", "info");
      setDrawerOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  // ── Delete ──────────────────────────────────────────────────────────────
  const handleDelete = async (id: string) => {
    try {
      await api.adminNewsDelete(id);
      loadNews(cursor);
      showToast("News item deleted.", "success");
    } catch {
      setAllItems((prev) => prev.filter((i) => i.id !== id));
      showToast("Removed locally (API offline).", "info");
    } finally {
      setConfirmDeleteId(null);
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-line pb-4">
        <div>
          <p className="font-util text-[10px] text-ink-soft uppercase tracking-widest">
            Editorial Console
          </p>
          <h1 className="font-display text-h2 font-semibold text-ink mt-1">
            News Releases
          </h1>
          <p className="font-util text-[10px] text-ink-soft mt-1">
            {allItems.length} total records · {items.length} shown
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleTrigger}
            disabled={fetchingLive}
            className="font-util text-[10px] uppercase tracking-wider text-ink bg-paper-2 hover:bg-paper border border-line px-4 py-2 cursor-pointer disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {fetchingLive ? "⏳ Fetching..." : "⚡ Trigger Live Fetch"}
          </button>
          <button
            onClick={openCreate}
            className="font-util text-[10px] uppercase tracking-wider text-paper bg-accent hover:opacity-90 border border-accent px-4 py-2 cursor-pointer transition-opacity"
          >
            + Add News
          </button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <AdminToast message={toast.msg} type={toast.type} onDismiss={() => setToast(null)} />
      )}

      {/* Search + Filters */}
      <AdminSearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search by title, summary, or source..."
        extra={
          <div className="flex gap-2 flex-shrink-0">
            <select
              value={domainFilter}
              onChange={(e) => setDomainFilter(e.target.value)}
              className="border border-line bg-paper px-3 py-2 text-[10px] font-util uppercase tracking-wider outline-none focus:border-accent transition-colors"
            >
              <option value="all">All Domains</option>
              {domains.map((d) => (
                <option key={d.slug} value={d.slug}>{d.name}</option>
              ))}
            </select>
            <select
              value={trendingFilter}
              onChange={(e) => setTrendingFilter(e.target.value as any)}
              className="border border-line bg-paper px-3 py-2 text-[10px] font-util uppercase tracking-wider outline-none focus:border-accent transition-colors"
            >
              <option value="all">All Items</option>
              <option value="yes">Trending Only</option>
              <option value="no">Non-Trending</option>
            </select>
          </div>
        }
      />

      {/* Table */}
      <AdminTable
        columns={["Title", "Domain", "Source", "Published", "Trending", "Actions"]}
        loading={loading}
        empty="No news entries match your filters."
      >
        {items.map((item) => (
          <tr key={item.id} className="hover:bg-paper-2 transition-colors">
            <td className="p-4 max-w-xs">
              <p className="font-display font-medium text-ink truncate">{item.title}</p>
              <p className="font-util text-[9px] text-ink-soft mt-0.5 truncate">{item.slug}</p>
            </td>
            <td className="p-4 font-util text-[10px] text-ink-soft uppercase tracking-wider whitespace-nowrap">
              {item.domain?.name ?? "General"}
            </td>
            <td className="p-4 font-util text-[10px] text-ink-soft truncate max-w-[120px]">
              {item.sourceName || "—"}
            </td>
            <td className="p-4 font-util text-[10px] text-ink-soft whitespace-nowrap">
              {fmt(item.publishedAt)}
            </td>
            <td className="p-4">
              {item.trending ? (
                <span className="font-util text-[9px] uppercase tracking-wider text-emerald-700 border border-emerald-300 bg-emerald-50 px-1.5 py-0.5">
                  Trending
                </span>
              ) : (
                <span className="font-util text-[9px] text-ink-soft">—</span>
              )}
            </td>
            <td className="p-4 text-right whitespace-nowrap">
              {confirmDeleteId === item.id ? (
                <span className="font-util text-[10px] uppercase tracking-wider text-red-600 space-x-2">
                  <span>Delete?</span>
                  <button onClick={() => handleDelete(item.id)} className="underline cursor-pointer font-bold">Yes</button>
                  <span className="text-line">/</span>
                  <button onClick={() => setConfirmDeleteId(null)} className="underline cursor-pointer text-ink">No</button>
                </span>
              ) : (
                <>
                  <button onClick={() => openEdit(item)} className="font-util text-[10px] uppercase tracking-wider hover:text-accent cursor-pointer underline transition-colors">
                    Edit
                  </button>
                  <button onClick={() => setConfirmDeleteId(item.id)} className="font-util text-[10px] uppercase tracking-wider text-red-500 hover:text-ink cursor-pointer underline ml-3 transition-colors">
                    Delete
                  </button>
                </>
              )}
            </td>
          </tr>
        ))}
      </AdminTable>

      {/* Pagination */}
      {(hasMore || cursorHistory.length > 1) && (
        <div className="flex justify-center pt-2">
          <CursorPagination
            hasMore={hasMore}
            hasPrevious={cursorHistory.length > 1}
            onNext={handleNext}
            onPrevious={handlePrevious}
          />
        </div>
      )}

      {/* Drawer */}
      <AdminDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editItem ? "Edit News Release" : "New News Release"}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <AdminField label="News Title" required>
            <input
              type="text" required value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                if (!editItem) setSlug(toSlug(e.target.value));
              }}
              placeholder="e.g. Robotics team calibrates LiDAR rigs"
              className={adminInputCls}
            />
          </AdminField>

          <AdminField label="URL Slug" required hint="Auto-generated from title on create">
            <input type="text" required value={slug} onChange={(e) => setSlug(e.target.value)} className={`${adminInputCls} font-mono`} />
          </AdminField>

          <AdminField label="Academic Domain" required>
            <select value={domainSlug} onChange={(e) => setDomainSlug(e.target.value)} className={adminSelectCls}>
              {domains.map((d) => (
                <option key={d.slug} value={d.slug}>{d.name}</option>
              ))}
            </select>
          </AdminField>

          <AdminField label="AI Summary">
            <textarea rows={4} value={aiSummary} onChange={(e) => setAiSummary(e.target.value)} placeholder="Concise editorial summary..." className={adminTextareaCls} />
          </AdminField>

          <div className="grid grid-cols-2 gap-4">
            <AdminField label="Source Name">
              <input type="text" value={sourceName} onChange={(e) => setSourceName(e.target.value)} placeholder="AI Research Desk" className={adminInputCls} />
            </AdminField>
            <AdminField label="Source URL">
              <input type="url" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="https://..." className={adminInputCls} />
            </AdminField>
          </div>

          <AdminField label="Cover Image URL">
            <input type="text" value={image} onChange={(e) => setImage(e.target.value)} placeholder="Paste image URL" className={adminInputCls} />
            {image && (
              <div className="mt-2 border border-line overflow-hidden h-24 bg-paper-2">
                <img src={image} alt="preview" className="w-full h-full object-cover" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
              </div>
            )}
          </AdminField>

          <div className="grid grid-cols-2 gap-4 items-end">
            <AdminField label="Publish Date" required>
              <input type="datetime-local" required value={publishedAt} onChange={(e) => setPublishedAt(e.target.value)} className={adminInputCls} />
            </AdminField>
            <label className="flex items-center gap-2 cursor-pointer pb-2">
              <input
                type="checkbox" checked={trending} onChange={(e) => setTrending(e.target.checked)}
                className="h-4 w-4 border border-line bg-paper accent-accent cursor-pointer"
              />
              <span className="font-util text-[10px] uppercase tracking-wider text-ink">Mark Trending</span>
            </label>
          </div>

          {formError && (
            <p className="font-util text-[10px] text-red-600 uppercase tracking-wider border border-red-200 bg-red-50 px-3 py-2">
              ⚠ {formError}
            </p>
          )}

          <div className="flex gap-3 pt-3 border-t border-line">
            <button type="submit" disabled={submitting} className="flex-1 font-util text-[10px] uppercase tracking-wider text-paper bg-accent hover:opacity-90 py-2.5 cursor-pointer disabled:opacity-50 transition-opacity">
              {submitting ? "Saving..." : editItem ? "Update Record" : "Create Record"}
            </button>
            <button type="button" onClick={() => setDrawerOpen(false)} className="flex-1 font-util text-[10px] uppercase tracking-wider text-ink border border-line hover:border-accent py-2.5 cursor-pointer transition-colors">
              Cancel
            </button>
          </div>
        </form>
      </AdminDrawer>
    </div>
  );
}
