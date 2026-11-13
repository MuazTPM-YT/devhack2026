import { connection } from "next/server";

import { OverviewView } from "@/components/overview/overview-view";
import { readServices } from "@/lib/config";

export const metadata = { title: "Overview" };

export default async function OverviewPage() {
  await connection(); // services.yaml read per request, not baked at build
  return <OverviewView services={await readServices()} />;
}
