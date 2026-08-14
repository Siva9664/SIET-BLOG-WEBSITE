export type Domain = { slug: string; name: string; count: number };
export type Tag = { slug: string; name: string };
export type Author = {
  id: string;
  name: string;
  role?: string;
  avatar?: string;
  department?: string;
};

export interface DetailedSection {
  heading: string;
  paragraphs: string[];
}

export interface CoverageEntry {
  id: string;
  sourceName: string;
  title: string;
  url: string;
  publishedAt: string;
  isPrimary?: boolean;
}

export interface NewsItem {
  id: string;
  slug: string;
  title: string;
  content?: string;
  aiSummary: string;
  simpleExplanation?: string;
  detailedSections?: DetailedSection[];
  contentDepth?: "full" | "summary_only" | string;
  contentSummary?: string;
  detailedSummary?: string;
  keyPoints?: string[];
  technicalDetails?: string;
  whyItMatters?: string;
  studentRelevance?: string;
  department?: string;
  subcategory?: string;
  canonicalUrl?: string;
  author?: string;
  verificationStatus?: "single_source" | "confirmed" | string;
  coverageCount?: number;
  coverage?: CoverageEntry[];
  sourceUrl: string;
  sourceName: string;
  domain: Domain;
  tags: Tag[] | string[];
  image?: string;
  publishedAt: string;
  trending?: boolean;
  likes: number;
  bookmarked?: boolean;
}

export interface Article {
  id: string;
  slug: string;
  title: string;
  excerpt: string;
  body: string;
  author: Author;
  domain: Domain;
  tags: Tag[];
  cover?: string;
  publishedAt: string;
  readingMinutes: number;
  likes: number;
  bookmarked?: boolean;
}

export interface MagazinePage {
  id: string;
  pageNumber: number;
  imageUrl: string;
  extractedText: string;
}

export interface MagazineTOCEntry {
  id: string;
  pageNumber: number;
  heading: string;
}

export interface MagazineIssue {
  id: string;
  slug: string;
  title: string;
  description: string;
  year: number;
  type: string;
  status?: "processing" | "published" | "failed" | string;
  failureReason?: string | null;
  pageCount?: number;
  pdfUrl?: string;
  coverImageUrl?: string;
  issueDate?: string;
  pages?: MagazinePage[];
  tocEntries?: MagazineTOCEntry[];
  gallery: string[];
  projectLinks: { label: string; url: string }[];
  likes: number;
  bookmarked?: boolean;
}

export interface Achievement extends MagazineIssue {
  student: Author;
  department: string;
  domain: Domain;
  certificateUrl?: string;
}

export interface Paginated<T> {
  items: T[];
  page: number;
  pages: number;
  total: number;
}

export interface CursorPageInfo {
  next_cursor: string | null;
  has_more: boolean;
}

export interface CursorPaginated<T> {
  items: T[];
  pageInfo: CursorPageInfo;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: "admin" | "user";
}

export interface SiteSettings {
  site_name: string;
  credit_line: string;
  accent_color: string;
  newsletter_enabled: boolean;
  featured_domains: string;
}
