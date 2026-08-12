"use client";

import * as React from "react";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import {
  AdminField,
  AdminToast,
  adminInputCls,
} from "@/components/admin/AdminShared";
import Link from "next/link";

// ─── Setting Section Wrapper ──────────────────────────────────────────────────
function SettingSection({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-line bg-paper">
      <div className="border-b border-line px-6 py-4 bg-paper-2">
        <h3 className="font-display text-sm font-semibold text-ink">{title}</h3>
        {subtitle && (
          <p className="font-util text-[10px] text-ink-soft uppercase tracking-wider mt-0.5">
            {subtitle}
          </p>
        )}
      </div>
      <div className="px-6 py-5 space-y-5">{children}</div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function AdminSettingsPage() {
  const [siteName, setSiteName] = useState("SIET News");
  const [creditLine, setCreditLine] = useState(
    "AI Research Lab · Sri Shakthi Institute of Engineering and Technology"
  );
  const [accentColor, setAccentColor] = useState("#0F2B5C");
  const [newsletterEnabled, setNewsletterEnabled] = useState(true);
  const [featuredDomains, setFeaturedDomains] = useState("machine-learning, robotics");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{
    msg: string;
    type: "success" | "error" | "info";
  } | null>(null);

  // Load from API
  useEffect(() => {
    let cancel = false;
    api
      .adminGetSettings()
      .then((res) => {
        if (!cancel && res) {
          if (res.site_name) setSiteName(res.site_name);
          if (res.credit_line) setCreditLine(res.credit_line);
          if (res.accent_color) setAccentColor(res.accent_color);
          if (res.newsletter_enabled !== undefined)
            setNewsletterEnabled(res.newsletter_enabled);
          if (res.featured_domains) setFeaturedDomains(res.featured_domains);
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancel) setLoading(false); });
    return () => { cancel = true; };
  }, []);

  const showToast = (
    msg: string,
    type: "success" | "error" | "info" = "success"
  ) => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.adminUpdateSettings({
        site_name: siteName,
        credit_line: creditLine,
        accent_color: accentColor,
        newsletter_enabled: newsletterEnabled,
        featured_domains: featuredDomains,
      });
      showToast("Settings saved successfully.", "success");
    } catch {
      showToast("Failed to save settings. Please try again.", "error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 gap-3">
        <div className="w-5 h-5 border-2 border-line border-t-accent rounded-full animate-spin" />
        <p className="font-util text-[10px] text-ink-soft uppercase tracking-wider">
          Loading settings...
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-3xl">
      {/* Header */}
      <div className="border-b border-line pb-4">
        <p className="font-util text-[10px] text-ink-soft uppercase tracking-widest">
          System Options
        </p>
        <h1 className="font-display text-h2 font-semibold text-ink mt-1">
          Console Settings
        </h1>
        <p className="font-util text-[10px] text-ink-soft mt-1">
          Changes here affect the live public website immediately.
        </p>
      </div>

      {/* Toast */}
      {toast && (
        <AdminToast message={toast.msg} type={toast.type} onDismiss={() => setToast(null)} />
      )}

      {/* Settings Form */}
      <form onSubmit={handleSave} className="space-y-6">

        {/* Branding */}
        <SettingSection
          title="Site Branding"
          subtitle="Controls masthead, footer, and meta tags"
        >
          <AdminField
            label="Site Masthead Title"
            hint="Appears in the navbar, browser title, and OG tags."
          >
            <input
              type="text"
              required
              value={siteName}
              onChange={(e) => setSiteName(e.target.value)}
              className={adminInputCls}
              placeholder="SIET News"
            />
          </AdminField>

          <AdminField
            label="Institute Credit Line"
            hint="Shown under the masthead and in the site footer."
          >
            <input
              type="text"
              required
              value={creditLine}
              onChange={(e) => setCreditLine(e.target.value)}
              className={adminInputCls}
              placeholder="AI Research Lab · Sri Shakthi Institute of Eng. & Tech."
            />
          </AdminField>

          <AdminField label="Brand Accent Color" hint="Controls active navigation, counters, and CTA elements.">
            <div className="flex gap-3 items-center">
              <input
                type="text"
                required
                value={accentColor}
                onChange={(e) => setAccentColor(e.target.value)}
                placeholder="#0F2B5C"
                className={`${adminInputCls} w-40 font-mono`}
              />
              <input
                type="color"
                value={accentColor}
                onChange={(e) => setAccentColor(e.target.value)}
                className="h-9 w-9 border border-line cursor-pointer bg-paper p-0.5"
                title="Pick accent color"
              />
              <div
                className="w-9 h-9 border border-line flex-shrink-0"
                style={{ backgroundColor: accentColor }}
                title="Color preview"
              />
              <span className="font-util text-[9px] text-ink-soft uppercase tracking-wider">
                Preview
              </span>
            </div>
          </AdminField>
        </SettingSection>

        {/* Content */}
        <SettingSection
          title="Content Configuration"
          subtitle="Controls which content surfaces on the homepage"
        >
          <AdminField
            label="Featured Domain Slugs"
            hint="Comma-separated domain slugs pinned to the homepage topic rail."
          >
            <input
              type="text"
              required
              value={featuredDomains}
              onChange={(e) => setFeaturedDomains(e.target.value)}
              placeholder="machine-learning, robotics, campus-research"
              className={`${adminInputCls} font-mono`}
            />
          </AdminField>

          <div className="flex items-start gap-3 py-1">
            <input
              id="newsletter-toggle"
              type="checkbox"
              checked={newsletterEnabled}
              onChange={(e) => setNewsletterEnabled(e.target.checked)}
              className="h-4 w-4 mt-0.5 border border-line bg-paper accent-accent cursor-pointer flex-shrink-0"
            />
            <div>
              <label
                htmlFor="newsletter-toggle"
                className="font-util text-[10px] uppercase tracking-wider text-ink cursor-pointer font-semibold"
              >
                Enable Footer Newsletter Form
              </label>
              <p className="font-util text-[9px] text-ink-soft mt-0.5">
                Shows an email subscription form in the footer. Disable if not using a newsletter provider.
              </p>
            </div>
          </div>
        </SettingSection>

        {/* Quick Links */}
        <SettingSection title="Quick Admin Navigation" subtitle="Shortcuts to other settings sections">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[
              { label: "Manage Domains", href: "/admin/domains", icon: "🗂️" },
              { label: "Manage Tags", href: "/admin/tags", icon: "🏷️" },
              { label: "User Access", href: "/admin/users", icon: "👥" },
              { label: "Media Library", href: "/admin/media", icon: "🖼️" },
              { label: "Analytics", href: "/admin/analytics", icon: "📊" },
              { label: "News Records", href: "/admin/news", icon: "📰" },
            ].map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="flex items-center gap-2 border border-line bg-paper-2 px-4 py-3 hover:border-accent hover:text-accent transition-colors font-util text-[10px] uppercase tracking-wider text-ink"
              >
                <span className="text-sm" role="img" aria-hidden="true">{link.icon}</span>
                {link.label}
              </Link>
            ))}
          </div>
        </SettingSection>

        {/* Save */}
        <div className="flex items-center gap-4 pt-2">
          <button
            type="submit"
            disabled={saving}
            className="font-util text-[10px] uppercase tracking-wider text-paper bg-accent hover:opacity-90 border border-accent py-2.5 px-8 cursor-pointer disabled:opacity-50 transition-opacity flex items-center gap-2"
          >
            {saving ? (
              <>
                <span className="inline-block w-3 h-3 border border-paper border-t-transparent rounded-full animate-spin" />
                Saving...
              </>
            ) : (
              "Save All Settings"
            )}
          </button>
          <p className="font-util text-[9px] text-ink-soft uppercase tracking-wider">
            Changes take effect immediately
          </p>
        </div>
      </form>

      {/* Danger Zone */}
      <div className="border border-red-200 bg-red-50">
        <div className="border-b border-red-200 px-6 py-4">
          <h3 className="font-display text-sm font-semibold text-red-700">Danger Zone</h3>
          <p className="font-util text-[10px] text-red-500 uppercase tracking-wider mt-0.5">
            Irreversible actions — proceed with caution
          </p>
        </div>
        <div className="px-6 py-5 space-y-3">
          {[
            {
              label: "Flush News Cache",
              desc: "Force all cached news records to expire and re-fetch from source.",
              btn: "Flush Cache",
            },
            {
              label: "Export All Content",
              desc: "Download a full JSON export of all news, articles, and magazine items.",
              btn: "Export JSON",
            },
          ].map((item) => (
            <div
              key={item.label}
              className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 py-3 border-b border-red-100 last:border-0"
            >
              <div>
                <p className="font-util text-[10px] uppercase tracking-wider text-red-700 font-semibold">
                  {item.label}
                </p>
                <p className="font-util text-[9px] text-red-500 mt-0.5">{item.desc}</p>
              </div>
              <button
                type="button"
                onClick={() => showToast(`${item.label} is not available in this environment.`, "info")}
                className="font-util text-[10px] uppercase tracking-wider border border-red-300 text-red-600 hover:bg-red-100 px-4 py-2 cursor-pointer transition-colors flex-shrink-0"
              >
                {item.btn}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
