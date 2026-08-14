"use client";

import * as React from "react";
import { useState, useEffect, useMemo } from "react";
import { api } from "@/lib/api";
import { CursorPagination, ErrorState } from "@/components/shared";
import {
  AdminDrawer,
  AdminTable,
  AdminField,
  AdminSearchBar,
  AdminToast,
  adminInputCls,
  adminTextareaCls,
  adminSelectCls,
} from "@/components/admin/AdminShared";
import type { Article, Domain } from "@/lib/types";

function toSlug(str: string) {
  return str.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}
function fmt(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export default function AdminArticlesCRUDPage() {
  const [allItems, setAllItems] = useState<Article[]>([]);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<(string | null)[]>([null]);
  const [hasMore, setHasMore] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" | "info" } | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [domainFilter, setDomainFilter] = useState("all");

  // Drawer
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editItem, setEditItem] = useState<Article | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  // Form fields
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [body, setBody] = useState("");
  const [authorName, setAuthorName] = useState("");
  const [authorRole, setAuthorRole] = useState("");
  const [authorDept, setAuthorDept] = useState("");
  const [authorAvatar, setAuthorAvatar] = useState("");
  const [domainSlug, setDomainSlug] = useState("");
  const [cover, setCover] = useState("");
  const [tagsCsv, setTagsCsv] = useState("");
  const [publishedAt, setPublishedAt] = useState("");
  const [readingMinutes, setReadingMinutes] = useState(5);

  // Filtered items
  const items = useMemo(() => {
    let list = allItems;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (i) =>
          i.title.toLowerCase().includes(q) ||
          i.excerpt?.toLowerCase().includes(q) ||
          i.author?.name.toLowerCase().includes(q)
      );
    }
    if (domainFilter !== "all") {
      list = list.filter((i) => i.domain?.slug === domainFilter);
    }
    return list;
  }, [allItems, search, domainFilter]);

  const showToast = (msg: string, type: "success" | "error" | "info" = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 5000);
  };

  const loadArticles = async (cur: string | null) => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await api.adminArticles(cur ? `?cursor=${cur}` : "");
      setAllItems(res.items || []);
      setHasMore(res.pageInfo.has_more);
      setNextCursor(res.pageInfo.next_cursor);
    } catch (err: any) {
      setAllItems([]);
      setLoadError(err?.message || "Failed to load research articles from backend API.");
      setHasMore(false);
      setNextCursor(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadArticles(cursor); }, [cursor]);
  useEffect(() => {
    api.domains().then(setDomains).catch(() => setDomains([]));
  }, []);

  const handleNext = () => {
    if (nextCursor) { setCursorHistory((h) => [...h, nextCursor]); setCursor(nextCursor); }
  };
  const handlePrevious = () => {
    if (cursorHistory.length > 1) {
      const h = cursorHistory.slice(0, -1);
      setCursorHistory(h);
      setCursor(h[h.length - 1]);
    }
  };

  const openCreate = () => {
    setEditItem(null);
    setTitle(""); setSlug(""); setExcerpt(""); setBody("");
    setAuthorName(""); setAuthorRole("Student Author"); setAuthorDept(""); setAuthorAvatar("");
    setDomainSlug(domains[0]?.slug || ""); setCover(""); setTagsCsv("");
    setPublishedAt(new Date().toISOString().substring(0, 16)); setReadingMinutes(5);
    setFormError(null); setDrawerOpen(true);
  };

  const openEdit = (item: Article) => {
    setEditItem(item);
    setTitle(item.title); setSlug(item.slug); setExcerpt(item.excerpt || ""); setBody(item.body || "");
    setAuthorName(item.author?.name || ""); setAuthorRole(item.author?.role || ""); setAuthorDept(item.author?.department || ""); setAuthorAvatar(item.author?.avatar || "");
    setDomainSlug(item.domain?.slug || domains[0]?.slug || ""); setCover(item.cover || "");
    setTagsCsv(item.tags?.map((t) => t.name).join(", ") || "");
    setPublishedAt(new Date(item.publishedAt).toISOString().substring(0, 16));
    setReadingMinutes(item.readingMinutes || 5);
    setFormError(null); setDrawerOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !slug || !domainSlug || !authorName) {
      setFormError("Title, Slug, Domain, and Author Name are required.");
      return;
    }
    setSubmitting(true);
    setFormError(null);
    const activeDomain = domains.find((d) => d.slug === domainSlug) || { slug: domainSlug, name: domainSlug, count: 0 };
    const tagsArray = tagsCsv.split(",").map((t) => t.trim()).filter(Boolean).map((tag) => ({ name: tag, slug: toSlug(tag) }));
    const payload = {
      title, slug, excerpt, body,
      author: { id: editItem?.author.id || `a-${Date.now()}`, name: authorName, role: authorRole, department: authorDept, avatar: authorAvatar },
      domain: activeDomain, cover, tags: tagsArray,
      publishedAt: new Date(publishedAt).toISOString(), readingMinutes: Number(readingMinutes),
    };
    try {
      if (editItem) { await api.adminArticlesUpdate(editItem.id, payload); showToast("Article updated.", "success"); }
      else { await api.adminArticlesCreate(payload); showToast("Article created.", "success"); }
      setDrawerOpen(false);
      loadArticles(cursor);
    } catch (err: any) {
      showToast(err?.message || "Failed to save article to server.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.adminArticlesDelete(id);
      loadArticles(cursor);
      showToast("Article deleted.", "success");
    } catch (err: any) {
      showToast(err?.message || "Failed to delete article.", "error");
    } finally {
      setConfirmDeleteId(null);
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-line pb-4">
        <div>
          <p className="font-util text-[10px] text-ink-soft uppercase tracking-widest">Editorial Console</p>
          <h1 className="font-display text-h2 font-semibold text-ink mt-1">Research Articles</h1>
          <p className="font-util text-[10px] text-ink-soft mt-1">{allItems.length} total · {items.length} shown</p>
        </div>
        <button onClick={openCreate} className="font-util text-[10px] uppercase tracking-wider text-paper bg-accent hover:opacity-90 border border-accent px-4 py-2 cursor-pointer transition-opacity">
          + Write Article
        </button>
      </div>

      {toast && <AdminToast message={toast.msg} type={toast.type} onDismiss={() => setToast(null)} />}

      {/* Search + filter */}
      <AdminSearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search by title, excerpt, or author..."
        extra={
          <select value={domainFilter} onChange={(e) => setDomainFilter(e.target.value)}
            className="border border-line bg-paper px-3 py-2 text-[10px] font-util uppercase tracking-wider outline-none focus:border-accent transition-colors flex-shrink-0"
          >
            <option value="all">All Domains</option>
            {domains.map((d) => (<option key={d.slug} value={d.slug}>{d.name}</option>))}
          </select>
        }
      />

      {loadError ? (
        <ErrorState title="Failed to Load Articles" message={loadError} onRetry={() => loadArticles(cursor)} />
      ) : (
        /* Table */
        <AdminTable columns={["Title", "Author", "Domain", "Reading", "Likes", "Published", "Actions"]} loading={loading} empty="No articles match your filters.">
          {items.map((item) => (
            <tr key={item.id} className="hover:bg-paper-2 transition-colors">
              <td className="p-4 max-w-xs">
                <p className="font-display font-medium text-ink truncate">{item.title}</p>
                <p className="font-util text-[9px] text-ink-soft mt-0.5 truncate">{item.slug}</p>
              </td>
              <td className="p-4">
                <p className="font-display text-xs text-ink">{item.author?.name ?? "—"}</p>
                <p className="font-util text-[9px] text-ink-soft uppercase tracking-wider">{item.author?.department?.split(" ")[0] || item.author?.role || ""}</p>
              </td>
              <td className="p-4 font-util text-[10px] text-ink-soft uppercase tracking-wider whitespace-nowrap">{item.domain?.name ?? "General"}</td>
              <td className="p-4 font-util text-[10px] text-ink-soft whitespace-nowrap">{item.readingMinutes} min</td>
              <td className="p-4 font-util text-[10px] text-ink-soft">♥ {item.likes}</td>
              <td className="p-4 font-util text-[10px] text-ink-soft whitespace-nowrap">{fmt(item.publishedAt)}</td>
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
                    <button onClick={() => openEdit(item)} className="font-util text-[10px] uppercase tracking-wider hover:text-accent cursor-pointer underline transition-colors">Edit</button>
                    <button onClick={() => setConfirmDeleteId(item.id)} className="font-util text-[10px] uppercase tracking-wider text-red-500 hover:text-ink cursor-pointer underline ml-3 transition-colors">Delete</button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </AdminTable>
      )}

      {(hasMore || cursorHistory.length > 1) && (
        <div className="flex justify-center pt-2">
          <CursorPagination hasMore={hasMore} hasPrevious={cursorHistory.length > 1} onNext={handleNext} onPrevious={handlePrevious} />
        </div>
      )}

      {/* Drawer */}
      <AdminDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title={editItem ? "Edit Article" : "Write New Article"}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <AdminField label="Article Title" required>
            <input type="text" required value={title}
              onChange={(e) => { setTitle(e.target.value); if (!editItem) setSlug(toSlug(e.target.value)); }}
              placeholder="e.g. Building retrieval systems with local embeddings" className={adminInputCls} />
          </AdminField>
          <AdminField label="URL Slug" required hint="Auto-generated; edit freely">
            <input type="text" required value={slug} onChange={(e) => setSlug(e.target.value)} className={`${adminInputCls} font-mono`} />
          </AdminField>
          <AdminField label="Academic Domain" required>
            <select value={domainSlug} onChange={(e) => setDomainSlug(e.target.value)} className={adminSelectCls}>
              {domains.map((d) => <option key={d.slug} value={d.slug}>{d.name}</option>)}
            </select>
          </AdminField>

          {/* Author block */}
          <div className="border border-line bg-paper-2 p-4 space-y-3 rounded-sm">
            <p className="font-util text-[9px] uppercase tracking-widest text-ink-soft border-b border-line pb-2">Author Details</p>
            <div className="grid grid-cols-2 gap-3">
              <AdminField label="Author Name" required>
                <input type="text" required value={authorName} onChange={(e) => setAuthorName(e.target.value)} placeholder="Jane Doe" className={adminInputCls} />
              </AdminField>
              <AdminField label="Author Role">
                <input type="text" value={authorRole} onChange={(e) => setAuthorRole(e.target.value)} placeholder="Student Author" className={adminInputCls} />
              </AdminField>
              <AdminField label="Department">
                <input type="text" value={authorDept} onChange={(e) => setAuthorDept(e.target.value)} placeholder="AI & DS" className={adminInputCls} />
              </AdminField>
              <AdminField label="Avatar URL">
                <input type="text" value={authorAvatar} onChange={(e) => setAuthorAvatar(e.target.value)} placeholder="https://..." className={adminInputCls} />
              </AdminField>
            </div>
          </div>

          <AdminField label="Short Excerpt">
            <input type="text" value={excerpt} onChange={(e) => setExcerpt(e.target.value)} placeholder="One-sentence summary..." className={adminInputCls} />
          </AdminField>
          <AdminField label="Body Content (HTML allowed)" hint="Wrap paragraphs in <p> tags">
            <textarea rows={8} value={body} onChange={(e) => setBody(e.target.value)} placeholder="<p>Write your article content here...</p>" className={adminTextareaCls} />
          </AdminField>
          <AdminField label="Cover Image URL">
            <input type="text" value={cover} onChange={(e) => setCover(e.target.value)} placeholder="Paste image URL" className={adminInputCls} />
            {cover && (
              <div className="mt-2 border border-line h-24 bg-paper-2 overflow-hidden">
                <img src={cover} alt="preview" className="w-full h-full object-cover" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
              </div>
            )}
          </AdminField>
          <AdminField label="Tags (comma-separated)">
            <input type="text" value={tagsCsv} onChange={(e) => setTagsCsv(e.target.value)} placeholder="RAG, Systems, Database" className={adminInputCls} />
          </AdminField>
          <div className="grid grid-cols-2 gap-4">
            <AdminField label="Publish Date" required>
              <input type="datetime-local" required value={publishedAt} onChange={(e) => setPublishedAt(e.target.value)} className={adminInputCls} />
            </AdminField>
            <AdminField label="Reading Minutes">
              <input type="number" min={1} required value={readingMinutes} onChange={(e) => setReadingMinutes(Number(e.target.value))} className={adminInputCls} />
            </AdminField>
          </div>

          {formError && <p className="font-util text-[10px] text-red-600 uppercase tracking-wider border border-red-200 bg-red-50 px-3 py-2">⚠ {formError}</p>}

          <div className="flex gap-3 pt-3 border-t border-line">
            <button type="submit" disabled={submitting} className="flex-1 font-util text-[10px] uppercase tracking-wider text-paper bg-accent hover:opacity-90 py-2.5 cursor-pointer disabled:opacity-50 transition-opacity">
              {submitting ? "Saving..." : editItem ? "Update Article" : "Publish Article"}
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
