"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";
import { TransparentLogo } from "@/components/shared";

interface AdminSidebarProps {
  user: User;
}

function getNavSections(role: string) {
  const isSuperAdmin = role?.toUpperCase() === "SUPER_ADMIN";

  const contentItems = [
    { label: "News Records", href: "/admin/news", icon: "📰", badge: null },
    { label: "Articles Desk", href: "/admin/articles", icon: "📄", badge: null },
  ];
  if (isSuperAdmin) {
    contentItems.push({ label: "Magazine Wins", href: "/admin/magazine", icon: "🏆", badge: null });
  }
  contentItems.push({ label: "Media Library", href: "/admin/media", icon: "🖼️", badge: null });

  const adminItems = [
    { label: "User Access", href: "/admin/users", icon: "👥", badge: null },
  ];
  if (isSuperAdmin) {
    adminItems.push({ label: "Manage Admins", href: "/admin/admins", icon: "🛡️", badge: null });
  }
  adminItems.push({ label: "System Settings", href: "/admin/settings", icon: "⚙️", badge: null });

  return [
    {
      label: "Overview",
      items: [
        { label: "Dashboard", href: "/admin", icon: "⬛", badge: null },
        { label: "Analytics", href: "/admin/analytics", icon: "📊", badge: null },
      ],
    },
    {
      label: "Content",
      items: contentItems,
    },
    {
      label: "Taxonomy",
      items: [
        { label: "Domains List", href: "/admin/domains", icon: "🗂️", badge: null },
        { label: "Tags Directory", href: "/admin/tags", icon: "🏷️", badge: null },
      ],
    },
    {
      label: "Administration",
      items: adminItems,
    },
  ];
}

export function AdminSidebar({ user }: AdminSidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [loggingOut, setLoggingOut] = React.useState(false);
  const [isOpen, setIsOpen] = React.useState(false);

  const handleLogout = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await api.logout();
      router.push("/admin/login");
      router.refresh();
    } catch (err) {
      console.error("Logout failed:", err);
      router.push("/admin/login");
    } finally {
      setLoggingOut(false);
    }
  };

  // Close mobile drawer on route change
  React.useEffect(() => {
    setIsOpen(false);
  }, [pathname]);

  const isActive = (href: string) => {
    if (href === "/admin") return pathname === "/admin";
    return pathname.startsWith(href);
  };

  const initials = user.name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <>
      {/* Mobile Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="lg:hidden fixed top-3.5 left-4 z-50 p-1.5 border border-line bg-paper text-ink hover:text-accent transition-colors cursor-pointer font-util text-[10px] uppercase tracking-wider outline-none focus:outline-2 focus:outline-accent"
        aria-expanded={isOpen}
        aria-label="Toggle Navigation Menu"
      >
        {isOpen ? "Close [×]" : "Menu [≡]"}
      </button>

      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          onClick={() => setIsOpen(false)}
          className="lg:hidden fixed inset-0 z-30 bg-paper/60 backdrop-blur-xs transition-opacity"
        />
      )}

      <aside className={`w-64 border-r border-line bg-paper-2 flex flex-col justify-between h-screen lg:sticky lg:top-0 font-util text-xs uppercase tracking-wider
        fixed inset-y-0 left-0 z-40 lg:z-auto transition-transform duration-300
        ${isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
      `}>
        {/* Top section: Brand & Navigation */}
        <div className="flex flex-col overflow-y-auto flex-1">
          {/* Brand Header */}
          <div className="p-5 border-b border-line flex-shrink-0">
            <Link href="/admin" className="font-display text-body font-semibold text-ink normal-case tracking-normal flex items-center gap-2.5 outline-none focus:outline-2 focus:outline-accent group">
              <div className="w-8 h-8 bg-accent flex items-center justify-center flex-shrink-0 group-hover:bg-ink transition-colors duration-200">
                <TransparentLogo
                  src="/api/logo"
                  alt="SIET Logo"
                  width={20}
                  height={20}
                  className="w-5 h-5 object-contain invert"
                />
              </div>
              <div className="min-w-0">
                <p className="font-display text-sm font-semibold text-ink leading-none truncate">SIET Admin</p>
                <p className="font-util text-[9px] text-ink-soft uppercase tracking-wider mt-0.5">Management Console</p>
              </div>
            </Link>
          </div>

          {/* Navigation by section */}
          <nav className="flex-1 py-4 px-3 space-y-5">
            {getNavSections(user.role).map((section) => (
              <div key={section.label}>
                <p className="font-util text-[9px] text-ink-soft uppercase tracking-widest px-2 mb-1.5">
                  {section.label}
                </p>
                <div className="space-y-0.5">
                  {section.items.map((item) => {
                    const active = isActive(item.href);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={`flex items-center gap-2.5 px-3 py-2 text-[11px] border transition-all duration-150 outline-none focus:outline-2 focus:outline-accent rounded-sm ${
                          active
                            ? "bg-accent text-paper border-accent shadow-sm"
                            : "border-transparent text-ink hover:border-line hover:bg-paper hover:text-accent"
                        }`}
                      >
                        <span className="text-xs leading-none opacity-70" role="img" aria-hidden="true">
                          {item.icon}
                        </span>
                        <span className="flex-1 truncate normal-case tracking-normal font-medium">{item.label}</span>
                        {active && (
                          <span className="w-1.5 h-1.5 rounded-full bg-paper/60 flex-shrink-0" />
                        )}
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>

          {/* View Public Site Link */}
          <div className="px-3 pb-3">
            <Link
              href="/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-3 py-2 border border-dashed border-line text-[10px] uppercase tracking-wider text-ink-soft hover:text-accent hover:border-accent transition-colors normal-case"
            >
              <span className="text-xs" role="img" aria-hidden="true">↗</span>
              <span className="tracking-wider">View Public Site</span>
            </Link>
          </div>
        </div>

        {/* Bottom section: User Info & Logout */}
        <div className="border-t border-line p-3 space-y-2 flex-shrink-0">
          {/* User Card */}
          <div className="flex items-center gap-2.5 px-2 py-2">
            <div className="w-8 h-8 bg-ink text-paper flex items-center justify-center text-[10px] font-util font-bold flex-shrink-0">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-display font-medium text-ink text-xs normal-case tracking-normal truncate leading-tight">
                {user.name}
              </p>
              <p className="font-util text-[9px] text-ink-soft uppercase tracking-wider truncate mt-0.5">
                {user.role}
              </p>
            </div>
          </div>

          {/* Logout Button */}
          <button
            onClick={handleLogout}
            disabled={loggingOut}
            className="w-full text-left px-3 py-2 border border-line hover:border-accent hover:text-accent transition-colors cursor-pointer bg-paper outline-none focus:outline-2 focus:outline-accent text-[10px] uppercase tracking-wider normal-case disabled:opacity-50"
          >
            {loggingOut ? "⏳ Logging out..." : "→ Log Out"}
          </button>
        </div>
      </aside>
    </>
  );
}
