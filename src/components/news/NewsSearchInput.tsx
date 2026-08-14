"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

interface NewsSearchInputProps {
  placeholder?: string;
  department?: string;
}

export function NewsSearchInput({
  placeholder = "Search across all active news (title, summary, tags, source)...",
  department = "",
}: NewsSearchInputProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") || "";

  const [query, setQuery] = React.useState(initialQuery);
  const [isPending, startTransition] = React.useTransition();

  // Sync state if URL changes externally
  React.useEffect(() => {
    setQuery(searchParams.get("q") || "");
  }, [searchParams]);

  // Debounce query changes to update URL
  React.useEffect(() => {
    const handler = setTimeout(() => {
      const currentQ = searchParams.get("q") || "";
      if (query !== currentQ) {
        startTransition(() => {
          const params = new URLSearchParams(searchParams.toString());
          if (query.trim()) {
            params.set("q", query.trim());
          } else {
            params.delete("q");
          }
          // Reset page on new query
          params.delete("page");

          const queryString = params.toString();
          router.push(`/news${queryString ? `?${queryString}` : ""}`);
        });
      }
    }, 300);

    return () => clearTimeout(handler);
  }, [query, router, searchParams]);

  const handleClear = () => {
    setQuery("");
    startTransition(() => {
      const params = new URLSearchParams(searchParams.toString());
      params.delete("q");
      params.delete("page");
      const queryString = params.toString();
      router.push(`/news${queryString ? `?${queryString}` : ""}`);
    });
  };

  return (
    <div className="relative w-full max-w-2xl">
      <div className="relative flex items-center">
        <span className="absolute left-3.5 text-ink-soft text-sm pointer-events-none" role="img" aria-label="search">
          🔍
        </span>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className="w-full bg-paper border border-line pl-10 pr-10 py-2.5 font-sans text-xs text-ink placeholder:text-ink-soft outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-all rounded-sm"
        />
        {isPending ? (
          <span className="absolute right-3 text-accent text-xs font-util animate-spin">
            ⏳
          </span>
        ) : query ? (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-3 text-ink-soft hover:text-ink text-xs font-util cursor-pointer"
            title="Clear search"
          >
            [×]
          </button>
        ) : null}
      </div>
      {query && (
        <p className="font-util text-[10px] text-ink-soft uppercase tracking-wider mt-1.5 pl-1">
          Searching across 90-day active feed {department ? `in department '${department.toUpperCase()}'` : ""}
        </p>
      )}
    </div>
  );
}
