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
  adminSelectCls,
} from "@/components/admin/AdminShared";
import type { User } from "@/lib/types";

// ─── Fallbacks ───────────────────────────────────────────────────────────────
const FALLBACK_USERS: User[] = [
  { id: "u1", name: "Srikumar B.", email: "editor@siet.edu", role: "admin" },
  { id: "u2", name: "Jane Doe", email: "jane@siet.edu", role: "user" },
];

// ─── Role Badge ───────────────────────────────────────────────────────────────
function RoleBadge({ role }: { role: string }) {
  const isAdmin = role === "admin";
  return (
    <span
      className={`font-util text-[9px] uppercase tracking-wider px-2 py-0.5 border ${
        isAdmin
          ? "border-accent/30 bg-accent/10 text-accent"
          : "border-line bg-paper-2 text-ink-soft"
      }`}
    >
      {role}
    </span>
  );
}

// ─── Avatar ───────────────────────────────────────────────────────────────────
function UserAvatar({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
  return (
    <div className="w-7 h-7 bg-ink text-paper flex items-center justify-center text-[9px] font-util font-bold flex-shrink-0">
      {initials}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function AdminUsersCRUDPage() {
  const [allItems, setAllItems] = useState<User[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" | "info" } | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<"all" | "admin" | "user">("all");

  // Drawer
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editItem, setEditItem] = useState<User | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  // Form fields
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"admin" | "user">("admin");
  const [password, setPassword] = useState("");

  // Filtered items
  const items = useMemo(() => {
    let list = allItems;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (i) =>
          i.name.toLowerCase().includes(q) ||
          i.email.toLowerCase().includes(q)
      );
    }
    if (roleFilter !== "all") {
      list = list.filter((i) => i.role === roleFilter);
    }
    return list;
  }, [allItems, search, roleFilter]);

  const showToast = (msg: string, type: "success" | "error" | "info" = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 5000);
  };

  const loadUsers = async () => {
    setLoading(true);
    try {
      const res = await api.adminUsers();
      setAllItems(res);
    } catch {
      setAllItems(FALLBACK_USERS);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
    api.me()
      .then(setCurrentUser)
      .catch(() => setCurrentUser(FALLBACK_USERS[0]));
  }, []);

  const openCreate = () => {
    setEditItem(null);
    setName(""); setEmail(""); setRole("admin"); setPassword("");
    setFormError(null); setDrawerOpen(true);
  };

  const openEdit = (item: User) => {
    setEditItem(item);
    setName(item.name); setEmail(item.email); setRole(item.role); setPassword("");
    setFormError(null); setDrawerOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || (!editItem && !password)) {
      setFormError("Name, Email, and Password (on create) are required.");
      return;
    }
    setSubmitting(true);
    setFormError(null);
    const payload: any = { name, email, role };
    if (password) payload.password = password;
    try {
      if (editItem) {
        await api.adminUserUpdate(editItem.id, payload);
        showToast("User updated successfully.", "success");
      } else {
        await api.adminUserCreate(payload);
        showToast("User created successfully.", "success");
      }
      setDrawerOpen(false);
      loadUsers();
    } catch {
      const mock: User = { id: editItem?.id || `u-${Date.now()}`, name, email, role };
      if (editItem) setAllItems((p) => p.map((i) => (i.id === editItem.id ? mock : i)));
      else setAllItems((p) => [...p, mock]);
      showToast("Saved locally (API offline).", "info");
      setDrawerOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.adminUserDelete(id);
      loadUsers();
      showToast("User removed.", "success");
    } catch {
      setAllItems((p) => p.filter((i) => i.id !== id));
      showToast("Removed locally (API offline).", "info");
    } finally {
      setConfirmDeleteId(null);
    }
  };

  const adminCount = allItems.filter((u) => u.role === "admin").length;
  const userCount = allItems.filter((u) => u.role === "user").length;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-line pb-4">
        <div>
          <p className="font-util text-[10px] text-ink-soft uppercase tracking-widest">Access Control</p>
          <h1 className="font-display text-h2 font-semibold text-ink mt-1">User Management</h1>
          <div className="flex items-center gap-4 mt-1">
            <span className="font-util text-[10px] text-ink-soft">{allItems.length} total accounts</span>
            <span className="font-util text-[9px] uppercase tracking-wider text-accent border border-accent/20 bg-accent/5 px-2 py-0.5">
              {adminCount} admin{adminCount !== 1 ? "s" : ""}
            </span>
            <span className="font-util text-[9px] uppercase tracking-wider text-ink-soft border border-line px-2 py-0.5">
              {userCount} user{userCount !== 1 ? "s" : ""}
            </span>
          </div>
        </div>
        <button
          onClick={openCreate}
          className="font-util text-[10px] uppercase tracking-wider text-paper bg-accent hover:opacity-90 border border-accent px-4 py-2 cursor-pointer transition-opacity"
        >
          + Add User
        </button>
      </div>

      {toast && <AdminToast message={toast.msg} type={toast.type} onDismiss={() => setToast(null)} />}

      {/* Search + filter */}
      <AdminSearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search by name or email..."
        extra={
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value as any)}
            className="border border-line bg-paper px-3 py-2 text-[10px] font-util uppercase tracking-wider outline-none focus:border-accent transition-colors flex-shrink-0"
          >
            <option value="all">All Roles</option>
            <option value="admin">Admins Only</option>
            <option value="user">Users Only</option>
          </select>
        }
      />

      {/* Table */}
      <AdminTable
        columns={["User", "Email", "Role", "Status", "Actions"]}
        loading={loading}
        empty="No users match your filters."
      >
        {items.map((item) => {
          const isSelf = currentUser?.id === item.id;
          return (
            <tr key={item.id} className={`hover:bg-paper-2 transition-colors ${isSelf ? "bg-accent/5" : ""}`}>
              <td className="p-4">
                <div className="flex items-center gap-2.5">
                  <UserAvatar name={item.name} />
                  <div>
                    <p className="font-display font-medium text-ink text-xs leading-tight">
                      {item.name}
                      {isSelf && (
                        <span className="font-util text-[8px] uppercase tracking-wider text-accent ml-2 border border-accent/20 px-1.5 py-0.5">
                          You
                        </span>
                      )}
                    </p>
                  </div>
                </div>
              </td>
              <td className="p-4 font-mono text-[10px] text-ink-soft">{item.email}</td>
              <td className="p-4"><RoleBadge role={item.role} /></td>
              <td className="p-4">
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  <span className="font-util text-[9px] uppercase tracking-wider text-ink-soft">Active</span>
                </span>
              </td>
              <td className="p-4 text-right whitespace-nowrap">
                {confirmDeleteId === item.id ? (
                  <span className="font-util text-[10px] uppercase tracking-wider text-red-600 space-x-2">
                    <span>{isSelf ? "Delete yourself?" : "Confirm?"}</span>
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
          );
        })}
      </AdminTable>

      {/* Drawer */}
      <AdminDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title={editItem ? "Edit User Profile" : "Register New User"}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <AdminField label="Full Name" required>
            <input type="text" required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Jane Doe" className={adminInputCls} />
          </AdminField>
          <AdminField label="Email Address" required>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="editor@siet.edu" className={adminInputCls} />
          </AdminField>
          <AdminField label="System Role" required hint="Admin role grants full access to all content management features.">
            <select value={role} onChange={(e) => setRole(e.target.value as "admin" | "user")} className={adminSelectCls}>
              <option value="admin">Administrator</option>
              <option value="user">Standard User</option>
            </select>
          </AdminField>
          <AdminField
            label={editItem ? "Reset Password (leave blank to keep current)" : "Password"}
            required={!editItem}
            hint={editItem ? "Only fill in to change the user's password." : undefined}
          >
            <input type="password" required={!editItem} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" className={adminInputCls} />
          </AdminField>

          {formError && (
            <p className="font-util text-[10px] text-red-600 uppercase tracking-wider border border-red-200 bg-red-50 px-3 py-2">⚠ {formError}</p>
          )}

          <div className="flex gap-3 pt-3 border-t border-line">
            <button type="submit" disabled={submitting} className="flex-1 font-util text-[10px] uppercase tracking-wider text-paper bg-accent hover:opacity-90 py-2.5 cursor-pointer disabled:opacity-50 transition-opacity">
              {submitting ? "Saving..." : editItem ? "Update User" : "Create User"}
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
