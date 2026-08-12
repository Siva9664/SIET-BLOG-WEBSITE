"use client";

import * as React from "react";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

interface TagItem {
  id: number;
  name: string;
  slug: string;
}

const FALLBACK_TAGS: TagItem[] = [
  { id: 1, name: "RAG Systems", slug: "rag-systems" },
  { id: 2, name: "Robotics", slug: "robotics" },
  { id: 3, name: "Machine Learning", slug: "machine-learning" },
  { id: 4, name: "AI Ethics", slug: "ai-ethics" },
];

export default function AdminTagsCRUDPage() {
  const [items, setItems] = useState<TagItem[]>([]);
  const [loading, setLoading] = useState(false);

  // Drawer / Form State
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editItem, setEditItem] = useState<TagItem | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Form Fields
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  // Delete Confirm ID
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

  // Load Data
  const loadTags = async () => {
    setLoading(true);
    try {
      const res = await api.adminTags();
      setItems(res);
    } catch (err) {
      console.warn("Admin tags API offline, loading static tags mock fallbacks.", err);
      setItems(FALLBACK_TAGS);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTags();
  }, []);

  // Open Drawer for Create
  const handleOpenCreate = () => {
    setEditItem(null);
    setName("");
    setSlug("");
    setFormError(null);
    setIsDrawerOpen(true);
  };

  // Open Drawer for Edit
  const handleOpenEdit = (item: TagItem) => {
    setEditItem(item);
    setName(item.name);
    setSlug(item.slug);
    setFormError(null);
    setIsDrawerOpen(true);
  };

  // Submit Drawer Form
  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !slug) {
      setFormError("Name and Slug fields are required.");
      return;
    }

    setSubmitting(true);
    setFormError(null);

    const payload = { name, slug };

    try {
      if (editItem) {
        await api.adminTagUpdate(editItem.id, payload);
      } else {
        await api.adminTagCreate(payload);
      }
      setIsDrawerOpen(false);
      loadTags();
    } catch (err) {
      console.error("Save failure:", err);
      const mockSavedItem: TagItem = {
        id: editItem?.id || Date.now(),
        name,
        slug,
      };

      if (editItem) {
        setItems(items.map((i) => (i.id === editItem.id ? mockSavedItem : i)));
      } else {
        setItems([...items, mockSavedItem]);
      }
      setIsDrawerOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  // Handle Delete
  const handleDelete = async (id: number) => {
    try {
      await api.adminTagDelete(id);
      loadTags();
    } catch (err) {
      console.warn("Delete call failed. Applying offline item removal.", err);
      setItems(items.filter((i) => i.id !== id));
    } finally {
      setConfirmDeleteId(null);
    }
  };

  return (
    <div className="space-y-6 relative min-h-[80vh]">
      {/* Page Header */}
      <div className="flex justify-between items-end border-b border-line pb-4">
        <div>
          <p className="font-util text-eyebrow text-ink-soft uppercase tracking-wider">
            editorial console
          </p>
          <h1 className="font-display text-h2 font-semibold text-ink mt-1">
            System Tags
          </h1>
        </div>
        <button
          onClick={handleOpenCreate}
          className="font-util text-eyebrow uppercase tracking-wider text-paper bg-ink hover:bg-accent border border-ink transition-colors px-4 py-2 cursor-pointer"
        >
          Add Tag
        </button>
      </div>

      {/* Main Table grid */}
      <div className="border border-line bg-paper">
        {loading ? (
          <div className="p-8 text-center font-display text-xs italic text-ink-soft">
            Querying tag records...
          </div>
        ) : items.length > 0 ? (
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-line bg-paper-2 font-util text-[10px] text-ink-soft uppercase tracking-wider">
                <th className="p-4 font-semibold">Tag Name</th>
                <th className="p-4 font-semibold">URL Slug</th>
                <th className="p-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-paper-2 transition-colors">
                  <td className="p-4 font-display font-medium text-ink">
                    {item.name}
                  </td>
                  <td className="p-4 font-mono text-ink-soft">#{item.slug}</td>
                  <td className="p-4 text-right space-x-3">
                    {confirmDeleteId === item.id ? (
                      <span className="font-util text-[10px] uppercase tracking-wider text-accent space-x-2">
                        <span>Confirm?</span>
                        <button
                          onClick={() => handleDelete(item.id)}
                          className="underline hover:text-ink cursor-pointer font-bold"
                        >
                          Yes
                        </button>
                        <span className="text-line">/</span>
                        <button
                          onClick={() => setConfirmDeleteId(null)}
                          className="underline hover:text-ink cursor-pointer"
                        >
                          Cancel
                        </button>
                      </span>
                    ) : (
                      <>
                        <button
                          onClick={() => handleOpenEdit(item)}
                          className="font-util text-[10px] uppercase tracking-wider hover:text-accent cursor-pointer underline"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(item.id)}
                          className="font-util text-[10px] uppercase tracking-wider text-accent hover:text-ink cursor-pointer underline"
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="p-8 text-center font-body text-xs italic text-ink-soft">
            No system tags exist in the database.
          </div>
        )}
      </div>

      {/* Drawer Overlay Backdrop */}
      {isDrawerOpen && (
        <div
          onClick={() => setIsDrawerOpen(false)}
          className="fixed inset-0 z-40 bg-paper/60 backdrop-blur-xs transition-opacity"
        />
      )}

      {/* Drawer Side Panel */}
      <div
        className={`fixed top-0 right-0 z-50 h-screen w-full max-w-lg border-l border-line bg-paper-2 p-6 overflow-y-auto transform transition-transform duration-300 ${
          isDrawerOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex justify-between items-center border-b border-line pb-3 mb-6">
          <h2 className="font-display text-body font-semibold text-ink">
            {editItem ? "Edit Tag" : "Add Tag"}
          </h2>
          <button
            onClick={() => setIsDrawerOpen(false)}
            className="font-util text-eyebrow uppercase tracking-wider hover:text-accent cursor-pointer text-xs"
          >
            Close [×]
          </button>
        </div>

        <form onSubmit={handleFormSubmit} className="space-y-4 text-xs">
          {/* Name */}
          <div className="space-y-1">
            <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
              Tag Name *
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (!editItem) {
                  setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""));
                }
              }}
              placeholder="e.g. Deep Learning"
              className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink"
            />
          </div>

          {/* Slug */}
          <div className="space-y-1">
            <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
              URL Slug *
            </label>
            <input
              type="text"
              required
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink font-mono"
            />
          </div>

          {/* Form Error */}
          {formError && (
            <p className="font-util text-[10px] text-accent uppercase tracking-wider">
              {formError}
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-4 pt-4 border-t border-line">
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 font-util text-eyebrow uppercase tracking-wider text-paper bg-ink hover:bg-accent border border-ink py-2 cursor-pointer disabled:opacity-50"
            >
              {submitting ? "Saving..." : "Save Record"}
            </button>
            <button
              type="button"
              onClick={() => setIsDrawerOpen(false)}
              className="flex-1 font-util text-eyebrow uppercase tracking-wider text-ink border border-line hover:bg-paper py-2 cursor-pointer"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
