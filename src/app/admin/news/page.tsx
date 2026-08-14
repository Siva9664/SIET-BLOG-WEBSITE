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
import type { NewsItem, Domain } from "@/lib/types";

// ─── Helper ──────────────────────────────────────────────────────────────────
function toSlug(str: string) {
  return str
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function fmt(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

// ─── Page ────────────────────────────────────────────────────────────────────
export default function AdminNewsCRUDPage() {
  const [allItems, setAllItems] = useState<NewsItem[]>([]);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<(string | null)[]>([null]);
  const [hasMore, setHasMore] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Search + Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"active" | "archived" | "all">("active");
  const [processingFilter, setProcessingFilter] = useState<"all" | "flagged_for_review" | "processed">("all");
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

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
    return list;
  }, [allItems, search]);

  // ── Load ────────────────────────────────────────────────────────────────
  const loadNews = async (cur: string | null) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (cur) params.set("cursor", cur);
      if (statusFilter) params.set("status", statusFilter);
      if (processingFilter !== "all") params.set("processing_status", processingFilter);
      if (departmentFilter !== "all") params.set("department", departmentFilter);
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);

      const q = params.toString() ? `?${params.toString()}` : "";
      const res = await api.adminNews(q);
      setAllItems(res.items || []);
      setHasMore(res.pageInfo.has_more);
      setNextCursor(res.pageInfo.next_cursor);
      setLoadError(null);
    } catch (err: any) {
      setAllItems([]);
      setLoadError(err?.message || "Failed to load news articles from backend API.");
      setHasMore(false);
      setNextCursor(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNews(cursor);
  }, [cursor, statusFilter, processingFilter, departmentFilter, startDate, endDate]);

  useEffect(() => {
    api.domains().then(setDomains).catch(() => setDomains([]));
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

    const payload = {
      title,
      slug,
      aiSummary,
      sourceName,
      sourceUrl,
      domainSlug,
      image,
      publishedAt: new Date(publishedAt).toISOString(),
      trending,
    };

    try {
      if (editItem) {
        await api.adminNewsUpdate(editItem.id, payload);
        showToast("News release updated successfully.");
      } else {
        await api.adminNewsCreate(payload);
        showToast("News release created successfully.");
      }
      setDrawerOpen(false);
      loadNews(cursor);
    } catch (err: any) {
      setFormError(err.message || "Failed to save news release.");
    } finally {
      setSubmitting(false);
    }
  };

  // ── Delete ──────────────────────────────────────────────────────────────
  const handleDelete = async (id: string) => {
    try {
      await api.adminNewsDelete(id);
      showToast("News release deleted.");
      setConfirmDeleteId(null);
      loadNews(cursor);
    } catch {
      showToast("Failed to delete entry.", "error");
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-line pb-4">
        <div>
          <p className="font-util text-[10px] text-ink-soft uppercase tracking-widest">
            Content Management · News Portal
          </p>
          <h1 className="font-display text-h2 font-semibold text-ink mt-1">
            News Releases & Archival Management
          </h1>
          <p className="font-util text-[11px] text-ink-soft mt-1">
            Manage active live feeds, inspect 30-day archived articles, and review accuracy grounding flags.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleTrigger}
            disabled={fetchingLive}
            className="font-util text-[10px] uppercase tracking-wider bg-paper-2 hover:bg-paper border border-line text-ink px-3 py-2 transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
          >
            <span>{fetchingLive ? "⏳" : "⚡"}</span>
            {fetchingLive ? "Ingesting..." : "Trigger Fetch"}
          </button>
          <button
            onClick={openCreate}
            className="font-util text-[10px] uppercase tracking-wider bg-accent hover:opacity-90 border border-accent text-paper px-4 py-2 transition-opacity cursor-pointer font-medium"
          >
            + Add News
          </button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <AdminToast message={toast.msg} type={toast.type} onDismiss={() => setToast(null)} />
      )}

      {/* Filter Toolbar */}
      <div className="bg-paper-2 border border-line p-4 rounded-md space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {/* Status Filter */}
          <div>
            <label className="block font-util text-[9px] uppercase tracking-wider text-ink-soft mb-1 font-bold">
              Archive Lifecycle
            </label>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value as any);
                setCursor(null);
                setCursorHistory([null]);
              }}
              className="w-full border border-line bg-paper px-2.5 py-1.5 text-xs font-util outline-none focus:border-accent"
            >
              <option value="active">Active Only (Live Site)</option>
              <option value="archived">Archived Only (30+ Days)</option>
              <option value="all">All News (Active & Archived)</option>
            </select>
          </div>

          {/* Processing / Accuracy Filter */}
          <div>
            <label className="block font-util text-[9px] uppercase tracking-wider text-ink-soft mb-1 font-bold">
              Grounding Check
            </label>
            <select
              value={processingFilter}
              onChange={(e) => {
                setProcessingFilter(e.target.value as any);
                setCursor(null);
                setCursorHistory([null]);
              }}
              className="w-full border border-line bg-paper px-2.5 py-1.5 text-xs font-util outline-none focus:border-accent"
            >
              <option value="all">All Statuses</option>
              <option value="flagged_for_review">⚠️ Flagged For Review</option>
              <option value="processed">✓ Verified & Grounded</option>
            </select>
          </div>

          {/* Department Filter */}
          <div>
            <label className="block font-util text-[9px] uppercase tracking-wider text-ink-soft mb-1 font-bold">
              Department Taxonomy
            </label>
            <select
              value={departmentFilter}
              onChange={(e) => {
                setDepartmentFilter(e.target.value);
                setCursor(null);
                setCursorHistory([null]);
              }}
              className="w-full border border-line bg-paper px-2.5 py-1.5 text-xs font-util outline-none focus:border-accent"
            >
              <option value="all">All Departments</option>
              <option value="ai-ml">AI & ML</option>
              <option value="cybersecurity">Cybersecurity</option>
              <option value="pcb-electronics">PCB & Electronics</option>
              <option value="vlsi-chips">VLSI & Chips</option>
              <option value="robotics">Robotics</option>
              <option value="ar-vr-xr">AR / VR / XR</option>
              <option value="iot-embedded">IoT & Embedded</option>
            </select>
          </div>

          {/* Start Date */}
          <div>
            <label className="block font-util text-[9px] uppercase tracking-wider text-ink-soft mb-1 font-bold">
              Published From
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full border border-line bg-paper px-2.5 py-1.5 text-xs font-util outline-none focus:border-accent"
            />
          </div>

          {/* End Date */}
          <div>
            <label className="block font-util text-[9px] uppercase tracking-wider text-ink-soft mb-1 font-bold">
              Published To
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full border border-line bg-paper px-2.5 py-1.5 text-xs font-util outline-none focus:border-accent"
            />
          </div>

          {/* Reset Filters */}
          <div className="flex items-end">
            <button
              onClick={() => {
                setStatusFilter("active");
                setProcessingFilter("all");
                setDepartmentFilter("all");
                setStartDate("");
                setEndDate("");
                setSearch("");
                setCursor(null);
                setCursorHistory([null]);
              }}
              className="w-full border border-line bg-paper hover:bg-paper-2 px-3 py-1.5 text-xs font-util uppercase tracking-wider text-ink-soft hover:text-ink transition-colors cursor-pointer"
            >
              Reset Filters
            </button>
          </div>
        </div>

        {/* Search Input */}
        <AdminSearchBar
          value={search}
          onChange={setSearch}
          placeholder="Search by title, summary, or source..."
        />
      </div>

      {/* Load Error State */}
      {loadError ? (
        <ErrorState
          title="Failed to Load News"
          message={loadError}
          onRetry={() => loadNews(cursor || null)}
        />
      ) : (
        /* Table */
        <AdminTable
          columns={["Title", "Department", "Source", "Published Date", "Archived At", "Status", "Actions"]}
          loading={loading}
          empty="No news entries match your filter criteria."
        >
        {items.map((item: any) => (
          <tr key={item.id} className="hover:bg-paper-2 transition-colors">
            <td className="p-4 max-w-xs">
              <div className="flex items-center gap-1.5 mb-1">
                {item.is_archived && (
                  <span className="px-1.5 py-0.5 text-[8px] font-bold font-util uppercase tracking-wider bg-purple-500/10 text-purple-700 border border-purple-500/30 rounded">
                    Archived
                  </span>
                )}
                {item.processing_status === "flagged_for_review" && (
                  <span className="px-1.5 py-0.5 text-[8px] font-bold font-util uppercase tracking-wider bg-amber-500/10 text-amber-700 border border-amber-500/30 rounded">
                    ⚠️ Flagged
                  </span>
                )}
                {!item.is_archived && item.processing_status !== "flagged_for_review" && (
                  <span className="px-1.5 py-0.5 text-[8px] font-bold font-util uppercase tracking-wider bg-emerald-500/10 text-emerald-700 border border-emerald-500/30 rounded">
                    Active
                  </span>
                )}
              </div>
              <p className="font-display font-medium text-ink truncate">{item.title}</p>
              <p className="font-util text-[9px] text-ink-soft truncate">{item.slug}</p>
            </td>
            <td className="p-4 font-util text-[10px] text-ink-soft uppercase tracking-wider whitespace-nowrap">
              {item.department || item.domain?.name || "General"}
            </td>
            <td className="p-4 font-util text-[10px] text-ink-soft truncate max-w-[120px]">
              {item.sourceName || "—"}
            </td>
            <td className="p-4 font-util text-[10px] text-ink-soft whitespace-nowrap">
              {fmt(item.publishedAt)}
            </td>
            <td className="p-4 font-util text-[10px] text-ink-soft whitespace-nowrap">
              {item.is_archived ? fmt(item.archived_at) : "—"}
            </td>
            <td className="p-4">
              {item.is_archived ? (
                <span className="font-util text-[9px] uppercase tracking-wider text-purple-700 border border-purple-300 bg-purple-50 px-1.5 py-0.5">
                  Vault (30d+)
                </span>
              ) : (
                <span className="font-util text-[9px] uppercase tracking-wider text-emerald-700 border border-emerald-300 bg-emerald-50 px-1.5 py-0.5">
                  Live Feed
                </span>
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
      )}

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
            <input type="url" value={image} onChange={(e) => setImage(e.target.value)} placeholder="https://..." className={adminInputCls} />
          </AdminField>

          <div className="grid grid-cols-2 gap-4">
            <AdminField label="Published Date" required>
              <input type="datetime-local" required value={publishedAt} onChange={(e) => setPublishedAt(e.target.value)} className={adminInputCls} />
            </AdminField>
            <AdminField label="Trending Status">
              <label className="flex items-center gap-2 mt-2 cursor-pointer">
                <input type="checkbox" checked={trending} onChange={(e) => setTrending(e.target.checked)} className="rounded text-accent" />
                <span className="font-util text-xs text-ink">Mark as Trending</span>
              </label>
            </AdminField>
          </div>

          {formError && (
            <p className="font-util text-xs text-red-600 bg-red-50 p-3 border border-red-200">{formError}</p>
          )}

          <div className="flex justify-end gap-3 pt-4 border-t border-line">
            <button type="button" onClick={() => setDrawerOpen(false)} className="px-4 py-2 border border-line text-xs font-util uppercase tracking-wider text-ink hover:bg-paper-2">
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="px-5 py-2 bg-accent text-paper text-xs font-util uppercase tracking-wider font-semibold hover:opacity-90 disabled:opacity-50">
              {submitting ? "Saving..." : editItem ? "Update Release" : "Publish Release"}
            </button>
          </div>
        </form>
      </AdminDrawer>
    </div>
  );
}
