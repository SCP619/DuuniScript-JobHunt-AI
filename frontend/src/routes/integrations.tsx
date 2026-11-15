import { createFileRoute } from "@tanstack/react-router";
import { Placeholder } from "@/components/app-shell";

export const Route = createFileRoute("/integrations")({
  head: () => ({
    meta: [
      { title: "Integrations — DuuniScript" },
      { name: "description", content: "Later, this page will let you connect optional services, such as your email or calendar, under your control." },
      { property: "og:title", content: "Integrations — DuuniScript" },
      { property: "og:description", content: "Later, this page will let you connect optional services, such as your email or calendar, under your control." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => <Placeholder title="Integrations" description="Later, this page will let you connect optional services, such as your email or calendar, under your control." />,
});
