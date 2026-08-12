"use client";

import * as React from "react";
import { useState, useEffect, useMemo } from "react";
import { api } from "@/lib/api";
import {
  AdminDrawer,
  AdminTable,
  AdminField,
  AdminSearchBar,
  AdminToast,
  adminInputCls,
} from "@/components/admin/AdminShared";
import type { Domain } from "@/lib/types";

const FALLBACK_DOMAINS: Domain[] = [
  { slug: "machine-learning", name: "Machine Learning", count: 42 },
  { slug: "robotics", name: "Robotics", count: 19 },
  { slug: "campus-research", name: "Campus Research", count: 27 },
  { slug: "ethics", name: "AI Ethics", count: 12 },
];

function toSlug(str: string) {
  return str.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

// Mini bar for domain size
function DomainBar({ count, max }: { count: number; max: number }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 bg-paper-2 border border-line h-1.5 overflow-hidden">
        <div className="bg-accent h-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="font-util text-[9px] text-ink-soft">{count}</span>
    </div>
  );
}

export default function AdminDomainsCRUDPage() {
  const [allItems, setAllItems] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" | "info" } | null>(null);
  const [search, setSearch] = useState("");

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editItem, setEditItem] = useState<Domain | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirmDeleteSlug, setConfirmDeleteSlug] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [count, setCount] = useState(0);

  const items = useMemo(() => {
    if (!search.trim()) return allItems;
    const q = search.toLowerCase();
    return allItems.filter((i) => i.name.toLowerCase().includes(q) || i.slug.includes(q));
  }, [allItems, search]);

  const maxCount = Math.max(...allItems.map((d) => d.count), 1);

  const showToast = (msg: string, type: "success" | "error" | "info" = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 5000);
  };

  const loadDomains = async () => {
    setLoading(true);
    try {
      const res = await api.adminDomains();
      setAllItems(res);
    } catch {
      api.domains().then(setAllItems).catch(() => setAllItems(FALLBACK_DOMAINS));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadDomains(); }, []);

  const openCreate = () => {
    setEditItem(null); setName(""); setSlug(""); setCount(0);
    setFormError(null); setDrawerOpen(true);
  };

  const openEdit = (item: Domain) => {
    setEditItem(item); setName(item.name); setSlug(item.slug); setCount(item.count || 0);
    setFormError(null); setDrawerOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !slug) { setFormError("Name and Slug are required."); return; }
    setSubmitting(true); setFormError(null);
    const payload = { name, slug, count: Number(count) };
    try {
      if (editItem) { await api.adminDomainUpdate(editItem.slug, payload); showToast("Domain updated.", "success"); }
      else { await api.adminDomainCreate(payload); showToast("Domain created.", "success"); }
      setDrawerOpen(false); loadDomains();
    } catch {
      if (editItem) setAllItems((p) => p.map((i) => (i.slug === editItem.slug ? payload : i)));
      else setAllItems((p) => [...p, payload]);
      showToast("Saved locally (API offline).", "info");
      setDrawerOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (targetSlug: string) => {
    try {
      await api.adminDomainDelete(targetSlug);
      loadDomains(); showToast("Domain removed.", "success");
    } catch {
      setAllItems((p) => p.filter((i) => i.slug !== targetSlug));
      showToast("Removed locally (API offline).", "info");
    } finally {
      setConfirmDeleteSlug(null);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-line pb-4">
        <div>
          <p className="font-util text-[10px] text-ink-soft uppercase tracking-widest">Taxonomy Console</p>
          <h1 className="font-display text-h2 font-semibold text-ink mt-1">Academic Domains</h1>
          <p className="font-util text-[10px] text-ink-soft mt-1">{allItems.length} domains · {allItems.reduce((s, d) => s + d.count, 0)} total entries</p>
        </div>
        <button onClick={openCreate} className="font-util text-[10px] uppercase tracking-wider text-paper bg-accent hover:opacity-90 border border-accent px-4 py-2 cursor-pointer transition-opacity">
          + Add Domain
        </button>
      </div>

      {toast && <AdminToast message={toast.msg} type={toast.type} onDismiss={() => setToast(null)} />}

      <AdminSearchBar value={search} onChange={setSearch} placeholder="Search domains by name or slug..." />

      <AdminTable columns={["Domain Name", "URL Slug", "Content Size", "Actions"]} loading={loading} empty="No domains match your search.">
        {items.map((item) => (
          <tr key={item.slug} className="hover:bg-paper-2 transition-colors">
            <td className="p-4">
              <p className="font-display font-medium text-ink">{item.name}</p>
            </td>
            <td className="p-4 font-mono text-[10px] text-ink-soft">{item.slug}</td>
            <td className="p-4">
              <DomainBar count={item.count} max={maxCount} />
            </td>
            <td className="p-4 text-right whitespace-nowrap">
              {confirmDeleteSlug === item.slug ? (
                <span className="font-util text-[10px] uppercase tracking-wider text-red-600 space-x-2">
                  <span>Delete?</span>
                  <button onClick={() => handleDelete(item.slug)} className="underline cursor-pointer font-bold">Yes</button>
                  <span className="text-line">/</span>
                  <button onClick={() => setConfirmDeleteSlug(null)} className="underline cursor-pointer text-ink">No</button>
                </span>
              ) : (
                <>
                  <button onClick={() => openEdit(item)} className="font-util text-[10px] uppercase tracking-wider hover:text-accent cursor-pointer underline transition-colors">Edit</button>
                  <button onClick={() => setConfirmDeleteSlug(item.slug)} className="font-util text-[10px] uppercase tracking-wider text-red-500 hover:text-ink cursor-pointer underline ml-3 transition-colors">Delete</button>
                </>
              )}
            </td>
          </tr>
        ))}
      </AdminTable>

      <AdminDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title={editItem ? "Edit Domain" : "Add New Domain"}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <AdminField label="Domain Name" required hint="Displayed in navigation and content cards.">
            <input type="text" required value={name}
              onChange={(e) => { setName(e.target.value); if (!editItem) setSlug(toSlug(e.target.value)); }}
              placeholder="e.g. Generative AI & LLMs" className={adminInputCls} />
          </AdminField>
          <AdminField label="URL Slug" required hint="Used in URLs — lowercase, hyphenated.">
            <input type="text" required value={slug} onChange={(e) => setSlug(e.target.value)} className={`${adminInputCls} font-mono`} />
          </AdminField>
          <AdminField label="Entry Count" hint="Override the displayed count of entries in this domain.">
            <input type="number" min={0} value={count} onChange={(e) => setCount(Number(e.target.value))} className={adminInputCls} />
          </AdminField>

          {formError && <p className="font-util text-[10px] text-red-600 uppercase tracking-wider border border-red-200 bg-red-50 px-3 py-2">⚠ {formError}</p>}

          <div className="flex gap-3 pt-3 border-t border-line">
            <button type="submit" disabled={submitting} className="flex-1 font-util text-[10px] uppercase tracking-wider text-paper bg-accent hover:opacity-90 py-2.5 cursor-pointer disabled:opacity-50 transition-opacity">
              {submitting ? "Saving..." : editItem ? "Update Domain" : "Create Domain"}
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
