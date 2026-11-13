import { Suspense } from "react";

import { LiveView } from "@/components/live/live-view";

export const metadata = { title: "Live incident" };

export default function LivePage() {
  return (
    <Suspense>
      <LiveView />
    </Suspense>
  );
}
