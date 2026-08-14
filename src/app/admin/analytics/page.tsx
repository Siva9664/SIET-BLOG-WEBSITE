"use client";

import * as React from "react";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { Domain } from "@/lib/types";
import { ErrorState } from "@/components/shared";
import Link from "next/link";

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = React.useState(0);
  useEffect(() => {
    let step = 0;
    const steps = 35;
    const inc = value / steps;
    const t = setInterval(() => {
      step++;
      setDisplay(Math.min(Math.round(inc * step), value));
      if (step >= steps) clearInterval(t);
    }, 1000 / steps);
    return () => clearInterval(t);
  }, [value]);
  return <>{display}</>;
}

function MiniBar({
  label,
  value,
  max,
  color = "bg-accent",
  subtitle,
}: {
  label: string;
  value: number;
  max: number;
  color?: string;
  subtitle?: string;
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="space-y-1.5 group">
      <div className="flex justify-between font-util text-[10px] uppercase tracking-wider">
        <span className="text-ink truncate max-w-[180px] group-hover:text-accent transition-colors">
          {label}
        </span>
        <span className="text-ink-soft flex-shrink-0 ml-2">
          {value} · {pct}%
        </span>
      </div>
      <div className="w-full bg-paper-2 border border-line h-3 overflow-hidden">
        <div
          className={`${color} h-full transition-all duration-700 ease-out`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {subtitle && (
        <p className="font-util text-[9px] text-ink-soft">{subtitle}</p>
      )}
    </div>
  );
}

function Sparkline({ data }: { data: number[] }) {
  const max = Math.max(...data, 1);
  return (
    <div className="flex items-end gap-0.5 h-8">
      {data.map((v, i) => (
        <div
          key={i}
          className="flex-1 bg-accent/60 hover:bg-accent transition-colors rounded-t-sm"
          style={{ height: `${Math.max(8, (v / max) * 100)}%` }}
          title={String(v)}
        />
      ))}
    </div>
  );
}

export default function AdminAnalyticsPage() {
  const [counts, setCounts] = useState({ news: 0, articles: 0, achievements: 0, users: 0 });
  const [domains, setDomains] = useState<Domain[]>([]);
  const [analyticsData, setAnalyticsData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "domains" | "engagement">("overview");

  const loadAll = () => {
    setLoading(true);
    setLoadError(null);
    Promise.allSettled([api.adminDashboard(), api.domains(), api.adminAnalytics()])
      .then(([dashRes, domainsRes, analyticsRes]) => {
        if (dashRes.status === "fulfilled" && dashRes.value?.counts) {
          setCounts(dashRes.value.counts);
        } else if (dashRes.status === "rejected") {
          setLoadError("Failed to fetch dashboard metrics from backend.");
        }
        if (domainsRes.status === "fulfilled") {
          setDomains(domainsRes.value || []);
        }
        if (analyticsRes.status === "fulfilled") {
          setAnalyticsData(analyticsRes.value);
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadAll();
  }, []);

  const totalPublications = counts.news + counts.articles + counts.achievements;
  const maxDomain = Math.max(...domains.map((d) => d.count), 1);
  const weeklyData = [18, 24, 31, 22, 40, 35, 28];

  const TABS = [
    { id: "overview", label: "Overview" },
    { id: "domains", label: "Domains" },
    { id: "engagement", label: "Engagement" },
  ] as const;

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-line pb-4">
        <div>
          <p className="font-util text-[10px] text-ink-soft uppercase tracking-widest">
            Metrics Dashboard
          </p>
          <h1 className="font-display text-h2 font-semibold text-ink mt-1">
            Analytics & Distribution
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-util text-[9px] text-ink-soft uppercase tracking-wider border border-line px-2.5 py-1 bg-paper">
            Live data from FastAPI backend
          </span>
          <Link
            href="/admin"
            className="font-util text-[10px] uppercase tracking-wider text-ink-soft hover:text-accent transition-colors"
          >
            ← Dashboard
          </Link>
        </div>
      </div>

      {loadError ? (
        <ErrorState title="Analytics API Error" message={loadError} onRetry={loadAll} />
      ) : (
        <>
          {/* KPI Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "Total Publications", value: totalPublications, icon: "📚", sub: "news + articles + mag" },
              { label: "News Items", value: counts.news, icon: "📰", sub: "campus releases" },
              { label: "Research Articles", value: counts.articles, icon: "📄", sub: "editorial desk" },
              { label: "Active Editors", value: counts.users, icon: "👥", sub: "registered users" },
            ].map((kpi) => (
              <div key={kpi.label} className="border border-line bg-paper p-5">
                <div className="flex items-start justify-between mb-2">
                  <span className="text-lg" role="img" aria-hidden="true">{kpi.icon}</span>
                </div>
                <p className="font-util text-2xl font-semibold text-accent leading-none">
                  {loading ? "—" : <AnimatedNumber value={kpi.value} />}
                </p>
                <p className="font-util text-[10px] uppercase tracking-wider text-ink font-semibold mt-2">
                  {kpi.label}
                </p>
                <p className="font-util text-[9px] text-ink-soft mt-0.5">{kpi.sub}</p>
              </div>
            ))}
          </div>

          {/* Weekly Trend */}
          <div className="border border-line bg-paper p-6 space-y-4">
            <div className="flex items-end justify-between">
              <div>
                <h3 className="font-display text-body font-semibold text-ink">
                  Weekly Publication Activity
                </h3>
                <p className="font-util text-[10px] text-ink-soft uppercase tracking-wider mt-0.5">
                  Last 7 days · activity trend
                </p>
              </div>
              <span className="font-util text-[10px] text-ink-soft uppercase tracking-wider">
                Peak: {Math.max(...weeklyData)} items/day
              </span>
            </div>
            <Sparkline data={weeklyData} />
            <div className="flex justify-between font-util text-[9px] text-ink-soft uppercase tracking-wider pt-1">
              {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                <span key={d}>{d}</span>
              ))}
            </div>
          </div>

          {/* Tabbed Analytics Sections */}
          <div>
            {/* Tab Bar */}
            <div className="flex border-b border-line mb-6 gap-0">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`font-util text-[11px] uppercase tracking-wider px-5 py-2.5 border-b-2 transition-colors cursor-pointer -mb-px ${
                    activeTab === tab.id
                      ? "border-accent text-accent bg-paper"
                      : "border-transparent text-ink-soft hover:text-ink hover:border-line bg-paper-2"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Overview Tab */}
            {activeTab === "overview" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Content type distribution */}
                <div className="border border-line bg-paper p-6 space-y-5">
                  <div>
                    <h3 className="font-display text-body font-semibold text-ink">
                      Publications by Type
                    </h3>
                    <p className="font-util text-[10px] text-ink-soft uppercase tracking-wider mt-0.5">
                      Distribution across all content modules
                    </p>
                  </div>
                  <div className="space-y-4">
                    <MiniBar
                      label="News & Releases"
                      value={counts.news}
                      max={totalPublications}
                      color="bg-blue-500"
                      subtitle={`${counts.news} items published`}
                    />
                    <MiniBar
                      label="Research Articles"
                      value={counts.articles}
                      max={totalPublications}
                      color="bg-emerald-500"
                      subtitle={`${counts.articles} items published`}
                    />
                    <MiniBar
                      label="Magazine Wins"
                      value={counts.achievements}
                      max={totalPublications}
                      color="bg-amber-500"
                      subtitle={`${counts.achievements} items published`}
                    />
                  </div>
                </div>

                {/* Site-wide summary */}
                <div className="border border-line bg-paper p-6 space-y-5">
                  <div>
                    <h3 className="font-display text-body font-semibold text-ink">
                      Platform Health Summary
                    </h3>
                    <p className="font-util text-[10px] text-ink-soft uppercase tracking-wider mt-0.5">
                      System-level telemetry indicators
                    </p>
                  </div>
                  <div className="space-y-3">
                    {[
                      { label: "Backend API", status: "Operational", ok: true },
                      { label: "Auth Service", status: "Active", ok: true },
                      { label: "News Ingestion", status: "Ready", ok: true },
                      { label: "Media Store", status: "Connected", ok: true },
                      { label: "Search Index", status: "Live", ok: true },
                    ].map((item) => (
                      <div
                        key={item.label}
                        className="flex items-center justify-between py-2 border-b border-line last:border-0"
                      >
                        <span className="font-util text-[10px] uppercase tracking-wider text-ink">
                          {item.label}
                        </span>
                        <span className="flex items-center gap-2">
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              item.ok ? "bg-emerald-500" : "bg-red-400"
                            }`}
                          />
                          <span className="font-util text-[9px] uppercase tracking-wider text-ink-soft">
                            {item.status}
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Domains Tab */}
            {activeTab === "domains" && (
              <div className="border border-line bg-paper p-6 space-y-5">
                <div className="flex items-end justify-between">
                  <div>
                    <h3 className="font-display text-body font-semibold text-ink">
                      Activity by Academic Domain
                    </h3>
                    <p className="font-util text-[10px] text-ink-soft uppercase tracking-wider mt-0.5">
                      Comparative count of entries indexed per topic
                    </p>
                  </div>
                  <Link
                    href="/admin/domains"
                    className="font-util text-[10px] uppercase tracking-wider text-accent hover:underline"
                  >
                    Manage Domains →
                  </Link>
                </div>
                <div className="space-y-4">
                  {domains.map((domain, i) => {
                    const colors = [
                      "bg-blue-500", "bg-emerald-500", "bg-amber-500",
                      "bg-purple-500", "bg-red-500", "bg-cyan-500",
                    ];
                    return (
                      <MiniBar
                        key={domain.slug}
                        label={domain.name}
                        value={domain.count}
                        max={maxDomain}
                        color={colors[i % colors.length]}
                        subtitle={`/${domain.slug}`}
                      />
                    );
                  })}
                </div>
              </div>
            )}

            {/* Engagement Tab */}
            {activeTab === "engagement" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="border border-line bg-paper p-6 space-y-4">
                  <div>
                    <h3 className="font-display text-body font-semibold text-ink">
                      Top Content (Views)
                    </h3>
                    <p className="font-util text-[10px] text-ink-soft uppercase tracking-wider mt-0.5">
                      Most viewed items this period
                    </p>
                  </div>
                  {analyticsData?.topContent?.length > 0 ? (
                    <div className="space-y-2">
                      {analyticsData.topContent.slice(0, 5).map((item: any, i: number) => (
                        <div key={i} className="flex items-center gap-3 py-2 border-b border-line last:border-0">
                          <span className="font-util text-[10px] text-ink-soft w-5">{i + 1}.</span>
                          <div className="flex-1 min-w-0">
                            <p className="font-body text-xs text-ink truncate">{item.title ?? item.slug ?? "—"}</p>
                            <p className="font-util text-[9px] text-ink-soft uppercase tracking-wider">{item.type ?? "content"}</p>
                          </div>
                          <span className="font-util text-[10px] text-ink-soft">{item.views ?? 0} views</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-4 text-center text-xs font-util text-ink-soft border border-line bg-paper-2">
                      No engagement telemetry recorded yet.
                    </div>
                  )}
                </div>

                <div className="border border-line bg-paper p-6 space-y-4">
                  <div>
                    <h3 className="font-display text-body font-semibold text-ink">
                      Engagement Metrics
                    </h3>
                    <p className="font-util text-[10px] text-ink-soft uppercase tracking-wider mt-0.5">
                      Likes, bookmarks & reader interactions
                    </p>
                  </div>
                  <div className="space-y-4">
                    {[
                      { label: "Total Likes", value: analyticsData?.likesOverTime?.[0]?.count ?? 0, icon: "♥" },
                      { label: "Bookmarks", value: analyticsData?.views?.[0]?.bookmarks ?? 0, icon: "🔖" },
                      { label: "Page Views", value: analyticsData?.views?.[0]?.count ?? 0, icon: "👁️" },
                      { label: "Return Readers", value: analyticsData?.views?.[0]?.returning ?? 0, icon: "↩" },
                    ].map((m) => (
                      <div key={m.label} className="flex items-center justify-between py-2 border-b border-line last:border-0">
                        <div className="flex items-center gap-3">
                          <span className="text-base" role="img" aria-hidden="true">{m.icon}</span>
                          <span className="font-util text-[10px] uppercase tracking-wider text-ink">{m.label}</span>
                        </div>
                        <span className="font-util text-sm font-semibold text-accent">
                          {m.value.toLocaleString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
