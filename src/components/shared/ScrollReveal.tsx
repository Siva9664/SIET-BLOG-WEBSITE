"use client";

import { useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";

export function ScrollReveal() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    let intersectionObserver: IntersectionObserver | null = null;
    let mutationObserver: MutationObserver | null = null;

    const observeElement = (el: Element) => {
      if (el.classList.contains("revealed")) return;

      const rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight + 100 && rect.bottom >= -100) {
        el.classList.add("revealed");
      } else {
        intersectionObserver?.observe(el);
      }
    };

    const scanAll = () => {
      const elements = document.querySelectorAll(".reveal");
      elements.forEach((el) => observeElement(el));
    };

    const rafId = requestAnimationFrame(() => {
      intersectionObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("revealed");
              intersectionObserver?.unobserve(entry.target);
            }
          });
        },
        {
          threshold: 0.01,
          rootMargin: "100px 0px 100px 0px",
        }
      );

      scanAll();

      mutationObserver = new MutationObserver(() => {
        scanAll();
      });

      mutationObserver.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["class"],
      });
    });

    return () => {
      cancelAnimationFrame(rafId);
      if (intersectionObserver) intersectionObserver.disconnect();
      if (mutationObserver) mutationObserver.disconnect();
    };
  }, [pathname, searchParams]);

  return null;
}
