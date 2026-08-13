"use client";

import { useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";

export function ScrollReveal() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    let observer: IntersectionObserver | null = null;

    // Postpone DOM mutations until React 19 hydration pass completes
    const rafId = requestAnimationFrame(() => {
      const elements = document.querySelectorAll(".reveal");

      observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("revealed");
              if (observer) observer.unobserve(entry.target);
            }
          });
        },
        {
          threshold: 0.01,
          rootMargin: "50px 0px 0px 0px",
        }
      );

      elements.forEach((el) => {
        const rect = el.getBoundingClientRect();
        if (rect.top < window.innerHeight && rect.bottom >= 0) {
          el.classList.add("revealed");
        } else {
          observer?.observe(el);
        }
      });
    });

    return () => {
      cancelAnimationFrame(rafId);
      if (observer) {
        observer.disconnect();
      }
    };
  }, [pathname, searchParams]);

  return null;
}
