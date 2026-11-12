import { Suspense } from "react";

import { LiveView } from "@/components/live/live-view";

export default function LivePage() {
  return (
    <Suspense>
      <LiveView />
    </Suspense>
  );
}
