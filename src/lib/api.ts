import type { Achievement, Article, Domain, MagazineIssue, NewsItem, Paginated, CursorPaginated, SiteSettings, User } from "./types";

const BASE = `${process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"}/api/v1`;

let currentUserPromise: Promise<User | null> | null = null;

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {};
  if (!(init?.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  try {
    const res = await fetch(`${BASE}${path}`, {
      credentials: "include",
      cache: "no-store",
      headers: { ...headers, ...init?.headers },
      ...init,
    });
    if (!res.ok) {
      if (res.status === 401) {
        currentUserPromise = null;
        if (typeof window !== "undefined") {
          localStorage.removeItem("siet_logged_in");
          localStorage.removeItem("siet_user_role");
        }
      }
      const errText = await res.text().catch(() => "");
      let errMsg = `API ${path} failed (${res.status})`;
      try {
        const jsonErr = JSON.parse(errText);
        if (jsonErr?.detail) errMsg += `: ${jsonErr.detail}`;
        else if (jsonErr?.message) errMsg += `: ${jsonErr.message}`;
        else if (errText) errMsg += `: ${errText}`;
      } catch {
        if (errText) errMsg += `: ${errText}`;
      }
      const err = new Error(errMsg);
      err.stack = err.message;
      throw err;
    }
    return res.json();
  } catch (err: any) {
    if (err.message && (err.message.includes("fetch failed") || err.cause?.code === "ECONNREFUSED")) {
      const cleanErr = new Error(`fetch failed: Connection refused to ${BASE}${path}`);
      cleanErr.stack = cleanErr.message;
      throw cleanErr;
    }
    if (err instanceof Error) {
      err.stack = err.message;
    }
    throw err;
  }
}

const normalizeDomain = (domain: any): Domain => {
  if (domain && typeof domain === "object" && domain.name) {
    return {
      slug: domain.slug || "general",
      name: domain.name || "General",
      count: Number(domain.count ?? 0),
    };
  }
  return { slug: "general", name: "General", count: 0 };
};

const normalizeAuthor = (author: any) => {
  if (author && typeof author === "object" && author.name) {
    return {
      id: String(author.id || "a1"),
      name: author.name || "Editorial Staff",
      role: author.role || "Author",
      avatar: author.avatar || "",
      department: author.department || "",
    };
  }
  return {
    id: "a1",
    name: "Editorial Staff",
    role: "Author",
    avatar: "",
    department: "",
  };
};

const normalizeStudent = (student: any) => {
  if (student && typeof student === "object" && student.name) {
    return {
      id: String(student.id || "s1"),
      name: student.name || "Student Researcher",
      role: student.role || "Contributor",
      avatar: student.avatar || "",
      department: student.department || "",
    };
  }
  return {
    id: "s1",
    name: "Student Researcher",
    role: "Contributor",
    avatar: "",
    department: "",
  };
};

const normalizeNewsItem = (item: any): NewsItem => ({
  id: String(item.id ?? ""),
  slug: item.slug ?? "",
  title: item.title ?? "",
  content: item.content ?? "",
  aiSummary: item.aiSummary ?? item.simple_explanation ?? item.contentSummary ?? item.excerpt ?? item.content ?? "",
  simpleExplanation: item.simple_explanation ?? item.simpleExplanation ?? item.contentSummary ?? item.aiSummary ?? "",
  detailedSections: Array.isArray(item.detailed_sections)
    ? item.detailed_sections.map((sec: any) => ({
      heading: sec.heading ?? "Overview",
      paragraphs: Array.isArray(sec.paragraphs) ? sec.paragraphs : [String(sec.paragraphs ?? "")],
    }))
    : Array.isArray(item.detailedSections)
      ? item.detailedSections
      : [
        {
          heading: "Overview",
          paragraphs: [item.detailedSummary ?? item.content ?? ""],
        },
      ],
  contentDepth: item.content_depth ?? item.contentDepth ?? "summary_only",
  contentSummary: item.contentSummary ?? item.simple_explanation ?? item.excerpt ?? "",
  detailedSummary: item.detailedSummary ?? item.content ?? "",
  keyPoints: Array.isArray(item.keyPoints)
    ? item.keyPoints
    : typeof item.keyPoints === "string"
      ? (function () { try { return JSON.parse(item.keyPoints); } catch { return [item.keyPoints]; } })()
      : Array.isArray(item.key_points) ? item.key_points : [],
  technicalDetails: item.technicalDetails ?? item.technical_details ?? "",
  whyItMatters: item.whyItMatters ?? item.why_it_matters ?? "",
  studentRelevance: item.studentRelevance ?? item.student_relevance ?? "",
  department: item.department ?? "",
  subcategory: item.subcategory ?? "",
  verificationStatus: item.verification_status ?? item.verificationStatus ?? "single_source",
  coverageCount: Number(item.coverage_count ?? item.coverageCount ?? (Array.isArray(item.coverage) ? item.coverage.length : 1)),
  coverage: Array.isArray(item.coverage)
    ? item.coverage.map((c: any) => ({
      id: String(c.id ?? ""),
      sourceName: c.source_name ?? c.sourceName ?? "Outlet",
      title: c.title ?? "",
      url: c.url ?? c.source_url ?? "",
      publishedAt: c.published_at ?? c.publishedAt ?? new Date().toISOString(),
      isPrimary: Boolean(c.is_primary ?? c.isPrimary),
    }))
    : [],
  sourceUrl: item.sourceUrl ?? "",
  sourceName: item.sourceName ?? "SIET News",
  domain: item.domain && typeof item.domain === "object" && item.domain.name
    ? normalizeDomain(item.domain)
    : {
      slug: item.department || "ai-ml",
      name: item.subcategory && item.subcategory !== "General"
        ? item.subcategory
        : (item.department ? item.department.toUpperCase().replace("-", " ") : "AI & ML"),
      count: 0,
    },
  tags: Array.isArray(item.tags) ? item.tags : [],
  image: item.image ?? item.cover ?? item.imageUrl ?? "",
  publishedAt: item.publishedAt ?? item.published_at ?? item.created_at ?? new Date().toISOString(),
  trending: Boolean(item.trending),
  likes: Number(item.likes ?? 0),
  bookmarked: Boolean(item.bookmarked),
});

const normalizeArticle = (item: any): Article => ({
  id: String(item.id ?? ""),
  slug: item.slug ?? "",
  title: item.title ?? "",
  excerpt: item.excerpt ?? "",
  body: item.body ?? item.content ?? "",
  author: normalizeAuthor(item.author),
  domain: normalizeDomain(item.domain),
  tags: Array.isArray(item.tags) ? item.tags : [],
  cover: item.cover ?? item.image ?? "",
  publishedAt: item.publishedAt ?? item.published_at ?? item.created_at ?? new Date().toISOString(),
  readingMinutes: Number(item.readingMinutes ?? item.reading_minutes ?? 5),
  likes: Number(item.likes ?? 0),
  bookmarked: Boolean(item.bookmarked),
});

const normalizeMagazine = (item: any): MagazineIssue => ({
  id: String(item.id ?? ""),
  slug: item.slug ?? "",
  title: item.title ?? "",
  description: item.description ?? "",
  year: Number(item.year ?? new Date().getFullYear()),
  type: item.type ?? "monthly",
  status: item.status ?? "published",
  failureReason: item.failureReason ?? item.failure_reason,
  pageCount: Number(item.pageCount ?? item.page_count ?? 0),
  pdfUrl: item.pdfUrl ?? item.pdf_url ?? item.certificateUrl,
  coverImageUrl: item.coverImageUrl ?? item.cover_image_url ?? (Array.isArray(item.gallery) && item.gallery.length > 0 ? item.gallery[0] : undefined),
  issueDate: item.issueDate ?? item.publishedAt ?? item.created_at ?? new Date().toISOString(),
  pages: Array.isArray(item.pages)
    ? item.pages.map((p: any) => ({
      id: String(p.id ?? ""),
      pageNumber: Number(p.pageNumber ?? p.page_number ?? 1),
      imageUrl: p.imageUrl ?? p.image_url ?? "",
      extractedText: p.extractedText ?? p.extracted_text ?? "",
    }))
    : [],
  tocEntries: Array.isArray(item.tocEntries)
    ? item.tocEntries.map((t: any) => ({
      id: String(t.id ?? ""),
      pageNumber: Number(t.pageNumber ?? t.page_number ?? 1),
      heading: t.heading ?? "",
    }))
    : [],
  latestAiNews: Array.isArray(item.latestAiNews) ? item.latestAiNews : [],
  gallery: Array.isArray(item.gallery) ? item.gallery : [],
  projectLinks: Array.isArray(item.projectLinks) ? item.projectLinks : [],
  likes: Number(item.likes ?? 0),
  bookmarked: Boolean(item.bookmarked),
});

const normalizeAchievement = (item: any): Achievement => ({
  ...normalizeMagazine(item),
  student: normalizeStudent(item.student),
  department: item.department ?? "",
  domain: normalizeDomain(item.domain),
  certificateUrl: item.certificateUrl ?? item.certificate_url,
});

function normalizePaginated<T>(res: any, mapItem: (x: any) => T): Paginated<T> {
  const rawItems = Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : [];
  const items = rawItems.map(mapItem);
  const page = res?.page ?? 1;
  const pages = res?.pages ?? (res?.pageInfo?.has_next ? page + 1 : page);
  const total = res?.total ?? items.length;
  return { items, page, pages, total };
}

function normalizeCursorPaginated<T>(res: any, mapItem: (x: any) => T): CursorPaginated<T> {
  const rawItems = Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : [];
  const items = rawItems.map(mapItem);
  const next_cursor = res?.pageInfo?.next_cursor ?? null;
  const has_more = Boolean(res?.pageInfo?.has_more ?? false);
  return {
    items,
    pageInfo: {
      next_cursor,
      has_more,
    },
  };
}

export const api = {
  login: async (b: { email: string; password: string }, init?: RequestInit) => {
    currentUserPromise = null;
    const res = await req<{ access_token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(b),
      ...init,
    });
    if (typeof window !== "undefined") {
      localStorage.setItem("siet_logged_in", "true");
      localStorage.setItem("siet_user_role", res.user.role);
      document.cookie = `access_token=${res.access_token}; path=/; max-age=604800; SameSite=Lax`;
    }
    currentUserPromise = Promise.resolve(res.user);
    return res.user;
  },
  logout: async (init?: RequestInit) => {
    currentUserPromise = null;
    const res = await req<unknown>("/auth/logout", { method: "POST", ...init });
    if (typeof window !== "undefined") {
      localStorage.removeItem("siet_logged_in");
      localStorage.removeItem("siet_user_role");
      document.cookie = "access_token=; path=/; max-age=0; SameSite=Lax";
    }
    currentUserPromise = Promise.resolve(null);
    return res;
  },
  me: (init?: RequestInit) => req<User>("/auth/me", init),
  getCurrentUser: (forceRefresh = false, init?: RequestInit): Promise<User | null> => {
    if (typeof window !== "undefined") {
      const isLogged = localStorage.getItem("siet_logged_in");
      if (isLogged !== "true") {
        currentUserPromise = Promise.resolve(null);
        return currentUserPromise;
      }
    }
    if (forceRefresh || !currentUserPromise) {
      currentUserPromise = req<User>("/auth/me", init).catch(() => {
        if (typeof window !== "undefined") {
          localStorage.removeItem("siet_logged_in");
          localStorage.removeItem("siet_user_role");
        }
        return null;
      });
    }
    return currentUserPromise;
  },
  clearUserCache: () => {
    currentUserPromise = null;
  },
  register: async (b: { name: string; email: string; password: string }, init?: RequestInit) => {
    currentUserPromise = null;
    return req<{ id: string; email: string; email_verified: boolean }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(b),
      ...init,
    });
  },

  likeStatus: (type: "news" | "articles" | "magazine", slug: string) =>
    req<{ liked: boolean; count: number }>(`/${type}/${slug}/like/status`),
  like: (type: "news" | "articles" | "magazine", slug: string) =>
    req<any>(`/${type}/${slug}/like`, { method: "POST" }),
  unlike: (type: "news" | "articles" | "magazine", slug: string) =>
    req<any>(`/${type}/${slug}/like`, { method: "DELETE" }),

  bookmarkStatus: (type: "news" | "articles" | "magazine", slug: string) =>
    req<{ bookmarked: boolean }>(`/${type}/${slug}/bookmark/status`),
  bookmark: (type: "news" | "articles" | "magazine", slug: string) =>
    req<any>(`/${type}/${slug}/bookmark`, { method: "POST" }),
  unbookmark: (type: "news" | "articles" | "magazine", slug: string) =>
    req<any>(`/${type}/${slug}/bookmark`, { method: "DELETE" }),

  myLikes: async () => {
    const data = await req<{ news?: NewsItem[]; articles?: Article[]; magazine?: Achievement[] }>("/me/likes");
    return {
      news: (data?.news || []).map(normalizeNewsItem),
      articles: (data?.articles || []).map(normalizeArticle),
      magazine: (data?.magazine || []).map(normalizeAchievement),
    };
  },
  myBookmarks: async () => {
    const data = await req<{ news?: NewsItem[]; articles?: Article[]; magazine?: Achievement[] }>("/me/bookmarks");
    return {
      news: (data?.news || []).map(normalizeNewsItem),
      articles: (data?.articles || []).map(normalizeArticle),
      magazine: (data?.magazine || []).map(normalizeAchievement),
    };
  },

  home: () => req("/home"),

  news: async (q = "") => {
    const res = await req<any>(`/news${q}`);
    return normalizePaginated(res, normalizeNewsItem);
  },
  newsBySlug: async (s: string) => {
    const res = await req<any>(`/news/${s}`);
    return normalizeNewsItem(res);
  },
  newsLatest: async () => {
    const res = await req<any[]>("/news/latest");
    return (Array.isArray(res) ? res : []).map(normalizeNewsItem);
  },
  newsTrending: async () => {
    const res = await req<any[]>("/news/trending");
    return (Array.isArray(res) ? res : []).map(normalizeNewsItem);
  },
  newsTaxonomy: async (q = "") => {
    return req<any>(`/news/taxonomy${q}`);
  },
  newsArchived: async (q = "") => {
    const res = await req<any>(`/news/archived${q}`);
    return normalizePaginated(res, normalizeNewsItem);
  },
  newsByDomain: async (d: string) => {
    const res = await req<any>(`/news/domain/${d}`);
    return normalizePaginated(res, normalizeNewsItem);
  },
  newsSearch: async (q: string) => {
    const res = await req<any>(`/news/search?q=${encodeURIComponent(q)}`);
    return normalizePaginated(res, normalizeNewsItem);
  },

  articles: async (q = "") => {
    const res = await req<any>(`/articles${q}`);
    return normalizePaginated(res, normalizeArticle);
  },
  articleBySlug: async (s: string) => {
    const res = await req<any>(`/articles/${s}`);
    return normalizeArticle(res);
  },
  articlesByDomain: async (d: string) => {
    const res = await req<any>(`/articles/domain/${d}`);
    return normalizePaginated(res, normalizeArticle);
  },

  magazine: async (q = "") => {
    const res = await req<any>(`/magazine${q}`);
    return normalizePaginated(res, normalizeMagazine);
  },
  magBySlug: async (s: string) => {
    const res = await req<any>(`/magazine/${s}`);
    return normalizeMagazine(res);
  },
  magByType: async (t: string) => {
    const res = await req<any>(`/magazine/type/${t}`);
    return normalizePaginated(res, normalizeMagazine);
  },
  magByYear: async (y: number) => {
    const res = await req<any>(`/magazine/year/${y}`);
    return normalizePaginated(res, normalizeMagazine);
  },
  magDownloadUrl: (slug: string) => `${BASE}/magazine/${slug}/download`,


  adminListMagazines: async () => {
    const data = await req<any>("/admin/magazine");
    const list = Array.isArray(data)
      ? data
      : Array.isArray(data?.data)
        ? data.data
        : Array.isArray(data?.magazines)
          ? data.magazines
          : Array.isArray(data?.items)
            ? data.items
            : [];
    return list.map(normalizeMagazine);
  },

  adminGetTemplate: async () => {
    return req<any>("/admin/magazine/template");
  },

  adminUpdateTemplate: async (data: { name?: string; section_schema: any[]; style_rules: any }) => {
    return req<any>("/admin/magazine/template", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  adminUploadTemplate: async (formData: FormData) => {
    return req<any>("/admin/magazine/template/upload", {
      method: "POST",
      body: formData,
    });
  },

  adminUploadMagazine: async (formData: FormData) => {
    return req<any>("/admin/magazine/upload", {
      method: "POST",
      body: formData,
    });
  },

  adminReplaceMagazinePdf: async (id: string, formData: FormData) => {
    return req<any>(`/admin/magazine/${id}/replace-pdf`, {
      method: "POST",
      body: formData,
    });
  },

  adminCreateEventMagazine: async (formData: FormData) => {
    return req<any>("/admin/magazine/create", {
      method: "POST",
      body: formData,
    });
  },

  adminUploadMagazineCover: async (id: string, formData: FormData) => {
    return req<any>(`/admin/magazine/${id}/cover`, {
      method: "POST",
      body: formData,
    });
  },

  adminUploadMagazineBody: async (id: string, formData: FormData) => {
    return req<any>(`/admin/magazine/${id}/body`, {
      method: "POST",
      body: formData,
    });
  },

  adminUploadMagazineGallery: async (id: string, formData: FormData) => {
    return req<any>(`/admin/magazine/${id}/gallery`, {
      method: "POST",
      body: formData,
    });
  },

  adminPublishMagazine: async (id: string) => {
    return req<{ message: string; id: string }>(`/admin/magazine/${id}/publish`, { method: "POST" });
  },

  adminUnpublishMagazine: async (id: string) => {
    return req<{ message: string; id: string }>(`/admin/magazine/${id}/unpublish`, { method: "POST" });
  },

  adminCompileMagazine: async (id: string) => {
    return req<{ message: string; id: string; pdf_url?: string; page_count?: number }>(`/admin/magazine/${id}/compile`, { method: "POST" });
  },

  // One-Click AI Auto-Fill for Event Magazine
  adminAutoGenerateFullMagazine: async (b: {
    event_name: string;
    event_date?: string;
    raw_notes: string;
    photo_count?: number;
  }) => {
    const res = await req<any>("/admin/magazine/ai/auto-generate", {
      method: "POST",
      body: JSON.stringify(b),
    });
    return (res?.data || res) as {
      magazine_issue_title: string;
      description: string;
      writeup_headline: string;
      writeup_html: string;
      writeup_text: string;
      captions: string[];
      toc_summary: string;
    };
  },

  adminAutoGenerateFromFile: async (formData: FormData) => {
    const res = await req<any>("/admin/magazine/ai/auto-generate-from-file", {
      method: "POST",
      body: formData,
    });
    return (res?.data || res) as {
      magazine_issue_title: string;
      description: string;
      writeup_headline: string;
      writeup_html: string;
      writeup_text: string;
      captions: string[];
      toc_summary: string;
      detected_event_name: string;
      detected_event_date: string;
      extracted_notes: string;
      extracted_images: { id: string; url: string; file_name: string }[];
    };
  },

  adminGenerateEndToEndMagazine: async (formData: FormData) => {
    const res = await req<any>("/admin/magazine/generate/end-to-end", {
      method: "POST",
      body: formData,
    });
    return (res?.data || res) as {
      magazine_id?: number | null;
      title: string;
      slug: string;
      department_or_lab: string;
      status: string;
      pdf_url?: string | null;
      cover_image_url?: string | null;
      total_pages: number;
      page_previews: string[];
      toc_entries: { page_number: number; heading: string }[];
      stage_telemetry: {
        stage_number: number;
        stage_name: string;
        status: string;
        message: string;
        details: Record<string, any>;
        elapsed_seconds: number;
      }[];
      qc_reports: any[];
      overall_quality_score: number;
      execution_time_seconds: number;
      notes: string;
    };
  },

  adminDeleteMagazine: async (id: string) => {
    return req<{ message: string }>(`/admin/magazine/${id}`, { method: "DELETE" });
  },

  domains: () => req<Domain[]>("/domains"),
  domain: (d: string) => req<Domain>(`/domains/${d}`),
  search: (q: string) => req(`/search?q=${encodeURIComponent(q)}`),

  adminDashboard: async () => {
    const data = await req<any>("/admin/dashboard");
    const counts = {
      news: data?.counts?.news ?? data?.totals?.news ?? 0,
      articles: data?.counts?.articles ?? data?.totals?.articles ?? 0,
      achievements: data?.counts?.achievements ?? data?.totals?.magazines ?? data?.totals?.achievements ?? 0,
      users: data?.counts?.users ?? data?.totals?.users ?? 0,
    };
    const todayAccuracy = data?.todayAccuracy ?? {
      date: new Date().toISOString().split("T")[0],
      verified: 0,
      flagged: 0,
      failed: 0,
      total: 0,
    };
    const recentActivity = Array.isArray(data?.recentActivity)
      ? data.recentActivity.map((act: any) => ({
        id: String(act.id ?? ""),
        action: act.action ?? act.type ?? "Update",
        timestamp: act.timestamp ?? act.created_at ?? new Date().toISOString(),
        details: act.details ?? act.title ?? "",
      }))
      : [];
    return { counts, todayAccuracy, recentActivity };
  },

  adminAnalytics: () => req<{ views: any[]; topContent: any[]; likesOverTime: any[] }>("/admin/analytics"),

  // Admin News
  adminNews: async (q = "") => {
    const res = await req<any>(`/admin/news${q}`);
    return normalizeCursorPaginated(res, normalizeNewsItem);
  },
  adminNewsCreate: async (b: any) => {
    const res = await req<any>("/admin/news", { method: "POST", body: JSON.stringify(b) });
    return normalizeNewsItem(res);
  },
  adminNewsUpdate: async (id: string, b: any) => {
    const res = await req<any>(`/admin/news/${id}`, { method: "PUT", body: JSON.stringify(b) });
    return normalizeNewsItem(res);
  },
  adminNewsDelete: (id: string) => req<{ success: boolean }>(`/admin/news/${id}`, { method: "DELETE" }),
  adminTriggerNewsFetch: () => req<{ message: string }>("/admin/news/trigger-fetch", { method: "POST" }),

  // Admin Articles
  adminArticles: async (q = "") => {
    const res = await req<any>(`/admin/articles${q}`);
    return normalizeCursorPaginated(res, normalizeArticle);
  },
  adminArticlesCreate: async (b: any) => {
    const res = await req<any>("/admin/articles", { method: "POST", body: JSON.stringify(b) });
    return normalizeArticle(res);
  },
  adminArticlesUpdate: async (id: string, b: any) => {
    const res = await req<any>(`/admin/articles/${id}`, { method: "PUT", body: JSON.stringify(b) });
    return normalizeArticle(res);
  },
  adminArticlesDelete: (id: string) => req<{ success: boolean }>(`/admin/articles/${id}`, { method: "DELETE" }),

  // Admin Magazine
  adminMagazine: async (q = "") => {
    const res = await req<any>(`/admin/magazine${q}`);
    return normalizeCursorPaginated(res, normalizeAchievement);
  },
  adminMagazineCreate: async (b: any) => {
    const res = await req<any>("/admin/magazine", { method: "POST", body: JSON.stringify(b) });
    return normalizeAchievement(res);
  },
  adminMagazineUpdate: async (id: string, b: any) => {
    const res = await req<any>(`/admin/magazine/${id}`, { method: "PUT", body: JSON.stringify(b) });
    return normalizeAchievement(res);
  },
  adminMagazineDelete: (id: string) => req<{ success: boolean }>(`/admin/magazine/${id}`, { method: "DELETE" }),

  // Admin Media
  adminMedia: () => req<{ id: string; url: string; filename: string; uploadedAt: string }[]>("/admin/media"),
  adminMediaUpload: (fd: FormData) => req<{ id: string; url: string; filename: string; uploadedAt: string }>("/admin/media/upload", { method: "POST", body: fd }),
  adminMediaDelete: (id: string) => req<{ success: boolean }>(`/admin/media/${id}`, { method: "DELETE" }),

  // Admin Domains
  adminDomains: () => req<Domain[]>("/admin/domains"),
  adminDomainCreate: (b: any) => req<Domain>("/admin/domains", { method: "POST", body: JSON.stringify(b) }),
  adminDomainUpdate: (slug: string, b: any) => req<Domain>(`/admin/domains/${slug}`, { method: "PUT", body: JSON.stringify(b) }),
  adminDomainDelete: (slug: string) => req<{ success: boolean }>(`/admin/domains/${slug}`, { method: "DELETE" }),

  // Admin Tags
  adminTags: () => req<{ id: number; name: string; slug: string }[]>("/admin/tags"),
  adminTagCreate: (b: any) => req<{ id: number; name: string; slug: string }>("/admin/tags", { method: "POST", body: JSON.stringify(b) }),
  adminTagUpdate: (id: number | string, b: any) => req<{ id: number; name: string; slug: string }>(`/admin/tags/${id}`, { method: "PUT", body: JSON.stringify(b) }),
  adminTagDelete: (id: number | string) => req<{ success: boolean }>(`/admin/tags/${id}`, { method: "DELETE" }),

  // Admin Users
  adminUsers: () => req<User[]>("/admin/users"),
  adminUserCreate: (b: any) => req<User>("/admin/users", { method: "POST", body: JSON.stringify(b) }),
  adminUserUpdate: (id: string, b: any) => req<User>(`/admin/users/${id}`, { method: "PUT", body: JSON.stringify(b) }),
  adminUserDelete: (id: string) => req<{ success: boolean }>(`/admin/users/${id}`, { method: "DELETE" }),

  // Admin Account Management (SUPER_ADMIN)
  adminAdmins: () => req<{ id: string; name: string; email: string; role: string; is_active: boolean; created_at: string }[]>("/admin/admins"),
  adminAdminCreate: (b: { name: string; email: string; password: string; role?: string }) =>
    req<{ id: string; name: string; email: string; role: string; is_active: boolean }>("/admin/admins", { method: "POST", body: JSON.stringify(b) }),
  adminAdminDelete: (id: string) => req<{ message: string }>(`/admin/admins/${id}`, { method: "DELETE" }),

  // Contact
  submitContact: (data: { name: string; email: string; subject?: string; message: string }) =>
    req<{ success: boolean }>("/contact", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Admin Settings
  adminGetSettings: () => req<SiteSettings>("/admin/settings"),
  adminUpdateSettings: (b: Partial<SiteSettings>) =>
    req<SiteSettings>("/admin/settings", { method: "PUT", body: JSON.stringify(b) }),
};
