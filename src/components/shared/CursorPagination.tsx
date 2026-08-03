import * as React from "react";

type CursorPaginationProps = {
  hasMore: boolean;
  hasPrevious: boolean;
  onNext: () => void;
  onPrevious: () => void;
};

export function CursorPagination({
  hasMore,
  hasPrevious,
  onNext,
  onPrevious,
}: CursorPaginationProps) {
  return (
    <nav aria-label="Pagination" className="pagination">
      <button
        type="button"
        aria-label="Previous page"
        disabled={!hasPrevious}
        onClick={onPrevious}
      >
        ‹
      </button>
      <span>page</span>
      <button
        type="button"
        aria-label="Next page"
        disabled={!hasMore}
        onClick={onNext}
      >
        ›
      </button>
    </nav>
  );
}
