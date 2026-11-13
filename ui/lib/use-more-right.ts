import { useEffect, useState } from "react";

// true while a sideways-scrolling box hides content past its right edge; drives the edge fade
export function useMoreRight(): [(el: HTMLElement | null) => void, boolean] {
  const [el, setEl] = useState<HTMLElement | null>(null);
  const [more, setMore] = useState(false);
  useEffect(() => {
    if (!el) return;
    const check = () => setMore(el.scrollWidth - el.clientWidth - el.scrollLeft > 4);
    check();
    el.addEventListener("scroll", check, { passive: true });
    const seen = new ResizeObserver(check);
    seen.observe(el);
    if (el.firstElementChild) seen.observe(el.firstElementChild);
    return () => { el.removeEventListener("scroll", check); seen.disconnect(); };
  }, [el]);
  return [setEl, more];
}
