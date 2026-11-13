"use client";

import { useEffect, useState } from "react";

// wall clock in epoch seconds, ticking only while something is running
export function useNow(running: boolean, everyMs = 1000): number {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!running) return;
    setNow(Date.now() / 1000);
    const id = setInterval(() => setNow(Date.now() / 1000), everyMs);
    return () => clearInterval(id);
  }, [running, everyMs]);
  return now;
}
