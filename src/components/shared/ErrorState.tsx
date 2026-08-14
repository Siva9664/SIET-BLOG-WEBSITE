import * as React from "react";
import Link from "next/link";

type ErrorStateProps = {
  title?: string;
  message?: string;
  onRetry?: () => void;
  actionHref?: string;
  actionLabel?: string;
};

export function ErrorState({
  title = "Failed to load content",
  message = "An error occurred while communicating with the backend services. Please check your connection or try again.",
  onRetry,
  actionHref,
  actionLabel = "Return Home",
}: ErrorStateProps) {
  return (
    <div className="border border-line bg-paper p-8 text-center space-y-4 max-w-xl mx-auto my-8">
      <div className="w-10 h-10 bg-rose-50 border border-rose-200 text-rose-600 rounded-full flex items-center justify-center mx-auto text-lg font-bold">
        !
      </div>
      <div>
        <h3 className="font-display text-h3 font-semibold text-ink">{title}</h3>
        <p className="font-body text-xs text-ink-soft mt-1 leading-relaxed">{message}</p>
      </div>
      <div className="flex justify-center gap-3 pt-2">
        {onRetry && (
          <button
            onClick={onRetry}
            className="font-util text-eyebrow uppercase tracking-wider text-paper bg-ink hover:bg-accent border border-ink px-4 py-2 transition-colors cursor-pointer"
          >
            Try Again
          </button>
        )}
        {actionHref && (
          <Link
            href={actionHref}
            className="font-util text-eyebrow uppercase tracking-wider text-ink border border-line hover:bg-paper-3 px-4 py-2 transition-colors"
          >
            {actionLabel}
          </Link>
        )}
      </div>
    </div>
  );
}
