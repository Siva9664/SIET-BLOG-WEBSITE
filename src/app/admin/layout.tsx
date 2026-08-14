import * as React from "react";
import { redirect } from "next/navigation";
import { headers } from "next/headers";
import { getSession } from "@/lib/auth";
import { AdminSidebar } from "@/components/admin/AdminSidebar";

export const metadata = {
  title: "Admin Console · SIET News",
  description: "Secure administration panel for SIET News Portal",
};

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const heads = await headers();
  const pathname = heads.get("x-pathname") || "";

  // Bypass auth gate specifically for the login page route
  if (pathname.includes("/admin/login")) {
    return <>{children}</>;
  }

  // Retrieve user session
  const user = await getSession();

  if (!user || !["SUPER_ADMIN", "ADMIN", "admin"].includes(user.role)) {
    redirect("/admin/login");
  }

  // Generate breadcrumb from route
  const pathParts = pathname.split("/").filter(Boolean).slice(1);
  const breadcrumbs = pathParts.map((p, idx) => ({
    label: p.charAt(0).toUpperCase() + p.slice(1).replace(/-/g, " "),
    href: "/" + ["admin", ...pathParts.slice(0, idx + 1)].join("/"),
  }));

  return (
    <div className="flex bg-paper text-ink min-h-screen">
      {/* Sidebar Navigation */}
      <AdminSidebar user={user} />

      {/* Main Admin Workspace */}
      <div className="flex-1 flex flex-col min-h-screen overflow-x-hidden">
        {/* Top Header Bar */}
        <header className="border-b border-line bg-paper px-6 py-3 flex justify-between items-center sticky top-0 z-10 shadow-sm">
          {/* Breadcrumb */}
          <nav className="flex items-center gap-1.5 font-util text-[10px] uppercase tracking-wider text-ink-soft pl-14 lg:pl-0">
            <span className="text-ink-soft">Admin</span>
            {breadcrumbs.map((crumb, i) => (
              <React.Fragment key={crumb.href}>
                <span className="text-line">/</span>
                <span className={i === breadcrumbs.length - 1 ? "text-ink font-semibold" : "text-ink-soft"}>
                  {crumb.label}
                </span>
              </React.Fragment>
            ))}
          </nav>

          {/* Status indicators */}
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
              <span className="font-util text-[9px] uppercase tracking-wider text-ink-soft">
                Secure Session
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 bg-accent flex items-center justify-center">
                <span className="font-util text-[9px] text-paper font-bold">
                  {user.name.split(" ").map((w: string) => w[0]).join("").toUpperCase().slice(0, 2)}
                </span>
              </div>
              <span className="hidden md:block font-util text-[10px] text-ink-soft uppercase tracking-wider">
                {user.name}
              </span>
            </div>
          </div>
        </header>

        {/* Workspace Body */}
        <div className="p-6 lg:p-8 flex-1">
          {children}
        </div>

        {/* Admin Footer */}
        <footer className="border-t border-line px-8 py-3 flex items-center justify-between">
          <p className="font-util text-[9px] text-ink-soft uppercase tracking-wider">
            SIET Admin Console · v2.0
          </p>
          <p className="font-util text-[9px] text-ink-soft uppercase tracking-wider">
            Sri Shakthi Institute of Engineering & Technology
          </p>
        </footer>
      </div>
    </div>
  );
}
