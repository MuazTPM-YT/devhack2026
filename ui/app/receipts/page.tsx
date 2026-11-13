import { Suspense } from "react";

import { ReceiptsView } from "@/components/receipts/receipts-view";

export const metadata = { title: "Receipts" };

export default function ReceiptsPage() {
  return (
    <Suspense>
      <ReceiptsView />
    </Suspense>
  );
}
