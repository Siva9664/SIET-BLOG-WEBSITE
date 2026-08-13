import { LoadingSkeleton } from "@/components/shared/LoadingSkeleton";

export default function NewsLoading() {
  return (
    <main className="kitchen-page">
      <header className="flex flex-col gap-2">
        <div className="h-4 w-24 bg-line/40 rounded animate-pulse" />
        <div className="h-10 w-64 bg-line/40 rounded animate-pulse" />
      </header>

      <div className="space-y-6 my-6">
        <div className="flex gap-6 border-b border-line pb-3">
          <div className="h-4 w-20 bg-line/40 rounded animate-pulse" />
          <div className="h-4 w-20 bg-line/40 rounded animate-pulse" />
          <div className="h-4 w-20 bg-line/40 rounded animate-pulse" />
        </div>
        <div className="flex gap-3">
          <div className="h-8 w-16 bg-line/40 rounded animate-pulse" />
          <div className="h-8 w-28 bg-line/40 rounded animate-pulse" />
          <div className="h-8 w-24 bg-line/40 rounded animate-pulse" />
        </div>
      </div>

      <LoadingSkeleton count={6} />
    </main>
  );
}
