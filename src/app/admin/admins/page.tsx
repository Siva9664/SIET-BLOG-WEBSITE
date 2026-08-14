"use client";

import * as React from "react";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";
import { ErrorState } from "@/components/shared";

interface AdminAccount {
  id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at?: string;
}

export default function AdminAdminsPage() {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [admins, setAdmins] = useState<AdminAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create Form Modal
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("ADMIN");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Delete State
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadAdmins = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.adminAdmins();
      setAdmins(data);
    } catch (err: any) {
      console.error("Failed to load admins:", err);
      setError(err?.message || "Failed to load admin accounts.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    api.getCurrentUser().then((u) => {
      setCurrentUser(u);
      setAuthChecked(true);
      if (u && u.role?.toUpperCase() === "SUPER_ADMIN") {
        loadAdmins();
      }
    });
  }, []);

  if (!authChecked) {
    return (
      <div className="p-8 text-center font-display text-xs italic text-ink-soft">
        Verifying administrative authorization...
      </div>
    );
  }

  if (authChecked && currentUser && currentUser.role?.toUpperCase() !== "SUPER_ADMIN") {
    return (
      <ErrorState
        title="Permission Denied"
        message="You do not have Super Administrator permissions required to manage administrative user accounts."
        onRetry={() => (window.location.href = "/admin")}
      />
    );
  }

  const handleOpenCreate = () => {
    setName("");
    setEmail("");
    setPassword("");
    setRole("ADMIN");
    setCreateError(null);
    setIsCreateOpen(true);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !password.trim()) {
      setCreateError("Please provide name, email, and temporary password.");
      return;
    }

    setCreating(true);
    setCreateError(null);

    try {
      await api.adminAdminCreate({
        name: name.trim(),
        email: email.trim(),
        password: password.trim(),
        role,
      });
      setIsCreateOpen(false);
      loadAdmins();
    } catch (err: any) {
      console.error("Create admin error:", err);
      setCreateError(err?.message || "Failed to create admin account.");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (targetAdmin: AdminAccount) => {
    setActionError(null);

    if (currentUser && String(currentUser.id) === String(targetAdmin.id)) {
      setActionError("You cannot delete your own administrative account.");
      setConfirmDeleteId(null);
      return;
    }

    if (targetAdmin.role.toUpperCase() === "SUPER_ADMIN") {
      const superAdminCount = admins.filter((a) => a.role.toUpperCase() === "SUPER_ADMIN").length;
      if (superAdminCount <= 1) {
        setActionError("Cannot delete account: At least one Super Administrator must remain registered.");
        setConfirmDeleteId(null);
        return;
      }
    }

    try {
      await api.adminAdminDelete(targetAdmin.id);
      loadAdmins();
    } catch (err: any) {
      console.error("Delete admin error:", err);
      setActionError(err?.message || "Failed to delete admin account.");
    } finally {
      setConfirmDeleteId(null);
    }
  };

  return (
    <div className="space-y-6 min-h-[80vh]">
      {/* Header */}
      <div className="flex justify-between items-end border-b border-line pb-4">
        <div>
          <p className="font-util text-eyebrow text-ink-soft uppercase tracking-wider">
            Super Admin Control
          </p>
          <h1 className="font-display text-h2 font-semibold text-ink mt-1">
            Administrative Accounts Management
          </h1>
        </div>
        <button
          onClick={handleOpenCreate}
          className="font-util text-eyebrow uppercase tracking-wider text-paper bg-ink hover:bg-accent border border-ink transition-colors px-4 py-2 cursor-pointer"
        >
          + Provision New Admin Account
        </button>
      </div>

      {actionError && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 font-util text-xs uppercase tracking-wider flex justify-between items-center">
          <span>⚠ {actionError}</span>
          <button onClick={() => setActionError(null)} className="cursor-pointer text-ink font-bold">
            [×]
          </button>
        </div>
      )}

      {/* Admins Table */}
      <div className="border border-line bg-paper">
        {loading ? (
          <div className="p-8 text-center font-display text-xs italic text-ink-soft">
            Querying administrative user registry...
          </div>
        ) : error ? (
          <div className="p-6 text-rose-700 bg-rose-50 border border-rose-200 font-util text-xs uppercase tracking-wider">
            {error}
          </div>
        ) : (
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-line bg-paper-2 font-util text-[10px] text-ink-soft uppercase tracking-wider">
                <th className="p-4 font-semibold">Administrator</th>
                <th className="p-4 font-semibold">Email Address</th>
                <th className="p-4 font-semibold">Access Level</th>
                <th className="p-4 font-semibold">Status</th>
                <th className="p-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {admins.map((adm) => {
                const isSelf = currentUser && String(currentUser.id) === String(adm.id);
                return (
                  <tr key={adm.id} className="hover:bg-paper-2 transition-colors">
                    <td className="p-4 font-display font-medium text-ink">
                      {adm.name} {isSelf && <span className="text-[10px] text-accent font-util uppercase ml-1">(You)</span>}
                    </td>
                    <td className="p-4 font-mono text-ink-soft text-[11px]">{adm.email}</td>
                    <td className="p-4">
                      {adm.role.toUpperCase() === "SUPER_ADMIN" ? (
                        <span className="inline-flex items-center gap-1 text-[10px] text-purple-700 bg-purple-50 px-2 py-0.5 border border-purple-200 uppercase tracking-wider font-semibold font-util">
                          🛡️ Super Admin
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[10px] text-blue-700 bg-blue-50 px-2 py-0.5 border border-blue-200 uppercase tracking-wider font-semibold font-util">
                          👤 Admin
                        </span>
                      )}
                    </td>
                    <td className="p-4 font-util">
                      {adm.is_active ? (
                        <span className="text-emerald-700 font-semibold text-[10px] uppercase tracking-wider">
                          Active
                        </span>
                      ) : (
                        <span className="text-rose-700 font-semibold text-[10px] uppercase tracking-wider">
                          Disabled
                        </span>
                      )}
                    </td>
                    <td className="p-4 text-right">
                      {confirmDeleteId === adm.id ? (
                        <span className="font-util text-[10px] uppercase tracking-wider text-accent space-x-2">
                          <span>Confirm deletion?</span>
                          <button
                            onClick={() => handleDelete(adm)}
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
                        <button
                          onClick={() => {
                            if (isSelf) {
                              setActionError("You cannot delete your own administrative account.");
                              return;
                            }
                            setConfirmDeleteId(adm.id);
                          }}
                          disabled={Boolean(isSelf)}
                          className="font-util text-[10px] uppercase tracking-wider text-accent hover:text-ink cursor-pointer underline disabled:opacity-40 disabled:no-underline"
                        >
                          Revoke / Delete
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Create Modal Drawer */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 bg-paper/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-md border border-line bg-paper-2 p-6 space-y-4 shadow-lg">
            <div className="flex justify-between items-center border-b border-line pb-3">
              <h2 className="font-display text-body font-semibold text-ink">
                Provision New Admin Account
              </h2>
              <button
                onClick={() => setIsCreateOpen(false)}
                className="font-util text-eyebrow text-ink-soft hover:text-ink uppercase tracking-wider text-xs"
              >
                [×]
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs">
              <div className="space-y-1">
                <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                  Full Name *
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Dr. Alex Morgan"
                  className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink"
                />
              </div>

              <div className="space-y-1">
                <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                  Email Address *
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="e.g. alex.m@siet.ac.in"
                  className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink"
                />
              </div>

              <div className="space-y-1">
                <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                  Initial Password *
                </label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Secure password..."
                  className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink"
                />
              </div>

              <div className="space-y-1">
                <label className="block font-util text-eyebrow text-ink-soft uppercase tracking-wider">
                  Role Permission Level
                </label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full border border-line bg-paper px-3 py-2 outline-none focus:border-ink font-util uppercase tracking-wider"
                >
                  <option value="ADMIN">ADMIN (News, Articles, Analytics, Logs)</option>
                  <option value="SUPER_ADMIN">SUPER_ADMIN (Full Privileges + Magazine &amp; Account Provisioning)</option>
                </select>
              </div>

              {createError && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 font-util text-[10px] uppercase tracking-wider">
                  {createError}
                </div>
              )}

              <div className="flex gap-3 pt-3 border-t border-line">
                <button
                  type="submit"
                  disabled={creating}
                  className="flex-1 font-util text-eyebrow uppercase tracking-wider text-paper bg-ink hover:bg-accent border border-ink py-2.5 cursor-pointer disabled:opacity-50"
                >
                  {creating ? "Creating Account..." : "Create Admin Account"}
                </button>
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 font-util text-eyebrow uppercase tracking-wider text-ink border border-line hover:bg-paper py-2.5 cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
