import { connection } from "next/server";

import { ServiceMap } from "@/components/map/service-map";
import { readServices } from "@/lib/config";

export const metadata = { title: "Service map" };

export default async function MapPage() {
  await connection(); // services.yaml read per request, not baked at build
  return <ServiceMap services={await readServices()} />;
}
