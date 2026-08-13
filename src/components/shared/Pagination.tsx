import Link from "next/link";

// ─── Contract ──────────────────────────────────────────────────────────────
// Accepts both the legacy prop names (page/pages/basePath) and the
// alternative names used by some callers (currentPage/totalPages/baseUrl).
// All props are optional — the component never crashes on undefined.
export interface PaginationProps {
  /** Current active page (1-indexed). Also accepted as `currentPage`. */
  page?: number;
  currentPage?: number;
  /** Total number of pages. Also accepted as `totalPages`. */
  pages?: number;
  totalPages?: number;
  /** Base URL for page links. Also accepted as `baseUrl`. */
  basePath?: string;
  baseUrl?: string;
}

/** Zero-crash number → "01" formatter */
function pad(value?: number): string {
  const safe = typeof value === "number" && isFinite(value) ? value : 0;
  return String(safe).padStart(2, "0");
}

export function Pagination({
  page,
  currentPage,
  pages,
  totalPages,
  basePath,
  baseUrl,
}: PaginationProps) {
  // Resolve aliased props with safe fallbacks
  const resolvedPage  = Math.max(1, page ?? currentPage ?? 1);
  const resolvedPages = Math.max(1, pages ?? totalPages ?? 1);
  const resolvedBase  = basePath ?? baseUrl ?? "#";

  if (process.env.NODE_ENV !== "production") {
    console.log("[Pagination] props:", {
      page, currentPage, pages, totalPages, basePath, baseUrl,
      resolvedPage, resolvedPages,
    });
  }

  // Don't render when there is only one page
  if (resolvedPages <= 1) return null;

  const previous = Math.max(resolvedPage - 1, 1);
  const next     = Math.min(resolvedPage + 1, resolvedPages);
  const separator = resolvedBase.includes("?") ? "&" : "?";

  const hasPrev = resolvedPage > 1;
  const hasNext = resolvedPage < resolvedPages;

  return (
    <nav aria-label="Pagination" className="pagination">
      {hasPrev ? (
        <Link
          aria-label="Previous page"
          href={`${resolvedBase}${separator}page=${previous}`}
        >
          ‹
        </Link>
      ) : (
        <span aria-disabled="true" className="pagination-disabled">‹</span>
      )}

      <span aria-current="page">
        {pad(resolvedPage)} / {pad(resolvedPages)}
      </span>

      {hasNext ? (
        <Link
          aria-label="Next page"
          href={`${resolvedBase}${separator}page=${next}`}
        >
          ›
        </Link>
      ) : (
        <span aria-disabled="true" className="pagination-disabled">›</span>
      )}
    </nav>
  );
}
