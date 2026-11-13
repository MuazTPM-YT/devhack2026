import { Suspense } from "react";

import { FlowView } from "@/components/flow/flow-view";

export const metadata = { title: "Flow · On-call" };

export default function FlowPage() {
  return (
    <Suspense>
      <FlowView />
    </Suspense>
  );
}
