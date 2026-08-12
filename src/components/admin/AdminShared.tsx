"use client";

import * as React from "react";

// ─── Shared Drawer wrapper ───────────────────────────────────────────────────
export function AdminDrawer({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  // Close on Escape key
  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          onClick={onClose}
          className="fixed inset-0 z-40 bg-ink/30 backdrop-blur-[2px] transition-opacity"
          aria-hidden="true"
        />
      )}

      {/* Panel */}
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`fixed top-0 right-0 z-50 h-screen w-full max-w-xl border-l border-line bg-paper shadow-2xl overflow-y-auto transform transition-transform duration-300 ease-out ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Drawer Header */}
        <div className="flex justify-between items-center border-b border-line px-6 py-4 sticky top-0 bg-paper z-10">
          <h2 className="font-display text-body font-semibold text-ink">{title}</h2>
          <button
            onClick={onClose}
            className="font-util text-[10px] uppercase tracking-wider hover:text-accent cursor-pointer text-ink-soft border border-line px-2.5 py-1.5 hover:border-accent transition-colors"
          >
            Close ×
          </button>
        </div>

        {/* Drawer Body */}
        <div className="px-6 py-5">{children}</div>
      </aside>
    </>
  );
}

// ─── Shared Table Shell ──────────────────────────────────────────────────────
export function AdminTable({
  columns,
  children,
  loading,
  empty,
}: {
  columns: string[];
  children: React.ReactNode;
  loading?: boolean;
  empty?: string;
}) {
  if (loading) {
    return (
      <div className="border border-line bg-paper p-12 text-center">
        <div className="inline-block w-6 h-6 border-2 border-line border-t-accent rounded-full animate-spin mb-3" />
        <p className="font-util text-[10px] text-ink-soft uppercase tracking-wider">
          Loading records...
        </p>
      </div>
    );
  }

  return (
    <div className="border border-line bg-paper overflow-x-auto">
      <table className="w-full text-left border-collapse text-xs min-w-[600px]">
        <thead>
          <tr className="border-b border-line bg-paper-2 font-util text-[10px] text-ink-soft uppercase tracking-wider">
            {columns.map((col) => (
              <th key={col} className={`p-4 font-semibold ${col === "Actions" ? "text-right" : ""}`}>
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {React.Children.count(children) === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="p-12 text-center font-body text-xs italic text-ink-soft"
              >
                {empty ?? "No records found."}
              </td>
            </tr>
          ) : (
            children
          )}
        </tbody>
      </table>
    </div>
  );
}

// ─── Shared Form Field ───────────────────────────────────────────────────────
export function AdminField({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label className="block font-util text-[10px] text-ink-soft uppercase tracking-wider">
        {label}
        {required && <span className="text-accent ml-1">*</span>}
      </label>
      {children}
      {hint && <p className="font-util text-[9px] text-ink-soft italic">{hint}</p>}
    </div>
  );
}

// ─── Shared form input ───────────────────────────────────────────────────────
export const adminInputCls =
  "w-full border border-line bg-paper px-3 py-2 outline-none focus:border-accent text-xs transition-colors";

export const adminTextareaCls =
  "w-full border border-line bg-paper px-3 py-2 outline-none focus:border-accent resize-y text-xs font-mono transition-colors";

export const adminSelectCls =
  "w-full border border-line bg-paper px-3 py-2 outline-none focus:border-accent font-util text-xs transition-colors";

// ─── Shared Delete Confirm ───────────────────────────────────────────────────
export function DeleteConfirmCell({
  id,
  confirmId,
  onConfirm,
  onCancel,
  onRequest,
}: {
  id: string;
  confirmId: string | null;
  onConfirm: (id: string) => void;
  onCancel: () => void;
  onRequest: (id: string) => void;
}) {
  if (confirmId === id) {
    return (
      <span className="font-util text-[10px] uppercase tracking-wider text-red-600 space-x-2 whitespace-nowrap">
        <span>Delete?</span>
        <button
          onClick={() => onConfirm(id)}
          className="underline hover:no-underline cursor-pointer font-bold"
        >
          Yes
        </button>
        <span className="text-line">/</span>
        <button
          onClick={onCancel}
          className="underline hover:no-underline cursor-pointer text-ink"
        >
          No
        </button>
      </span>
    );
  }
  return (
    <>
      <button className="font-util text-[10px] uppercase tracking-wider hover:text-accent cursor-pointer underline transition-colors">
        Edit
      </button>
      <button
        onClick={() => onRequest(id)}
        className="font-util text-[10px] uppercase tracking-wider text-red-500 hover:text-ink cursor-pointer underline ml-3 transition-colors"
      >
        Delete
      </button>
    </>
  );
}

// ─── Search + Filter Bar ─────────────────────────────────────────────────────
export function AdminSearchBar({
  value,
  onChange,
  placeholder = "Search records...",
  extra,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  extra?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center">
      <div className="relative flex-1">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-soft text-xs">⌕</span>
        <input
          type="search"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full border border-line bg-paper pl-8 pr-3 py-2 outline-none focus:border-accent text-xs font-util uppercase tracking-wider transition-colors"
        />
      </div>
      {extra}
    </div>
  );
}

// ─── Empty State ─────────────────────────────────────────────────────────────
export function AdminEmptyState({
  icon = "📭",
  title = "No records found",
  action,
}: {
  icon?: string;
  title?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="border border-dashed border-line bg-paper-2 p-12 text-center space-y-3">
      <span className="text-3xl" role="img" aria-hidden="true">{icon}</span>
      <p className="font-display text-sm text-ink-soft">{title}</p>
      {action && <div>{action}</div>}
    </div>
  );
}

// ─── Toast Notification ───────────────────────────────────────────────────────
export function AdminToast({
  message,
  type = "success",
  onDismiss,
}: {
  message: string;
  type?: "success" | "error" | "info";
  onDismiss: () => void;
}) {
  const colors = {
    success: "border-emerald-300 bg-emerald-50 text-emerald-700",
    error: "border-red-300 bg-red-50 text-red-700",
    info: "border-blue-300 bg-blue-50 text-blue-700",
  };
  const icons = { success: "✓", error: "✕", info: "ℹ" };

  return (
    <div
      className={`border px-4 py-3 text-xs font-util uppercase tracking-wider flex items-center justify-between gap-4 ${colors[type]}`}
    >
      <span className="flex items-center gap-2">
        <span>{icons[type]}</span>
        {message}
      </span>
      <button onClick={onDismiss} className="cursor-pointer hover:opacity-70 transition-opacity">
        ×
      </button>
    </div>
  );
}
