import { createFileRoute } from "@tanstack/react-router";
import Fathom from "@/components/Fathom";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Tidal Wave — See the future of the California Current" },
      { name: "description", content: "Tidal Wave is an ocean ecosystem simulator. Type a policy, watch the California Current respond — species, kelp, urchins, sea lions, year by year." },
      { property: "og:title", content: "Tidal Wave — See the future" },
      { property: "og:description", content: "Simulate ocean policies on the California Current ecosystem." },
    ],
  }),
  component: Index,
});

function Index() {
  return <Fathom />;
}
