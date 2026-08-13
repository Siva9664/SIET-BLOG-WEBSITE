type LoadingSkeletonProps = {
  /** Number of skeleton rows. */
  lines?: number;
  /** Alias for `lines` — accepted for backward compat. */
  count?: number;
};

export function LoadingSkeleton({ lines, count = 4 }: LoadingSkeletonProps) {
  const rows = lines ?? count;
  return (
    <div aria-label="Loading" className="loading-skeleton" role="status">
      <div />
      {Array.from({ length: rows }).map((_, index) => (
        <span key={index} />
      ))}
    </div>
  );
}
