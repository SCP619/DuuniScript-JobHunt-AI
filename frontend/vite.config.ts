import { defineConfig, loadEnv } from "vite";
import tailwindcss from "@tailwindcss/vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig(async ({ command, mode }) => {
  const plugins = [
    tailwindcss(),
    tanstackStart({
      // Server-only code must never reach the browser bundle.
      importProtection: { behavior: "error", client: { files: ["**/server/**"], specifiers: ["server-only"] } },
      // Use src/server.ts (the SSR error wrapper) as the server entry.
      server: { entry: "server" },
    }),
  ];
  if (command === "build") {
    const { nitro } = await import("nitro/vite");
    plugins.push(nitro({ preset: "node-server" }));
  }
  plugins.push(viteReact());

  const define: Record<string, string> = {};
  for (const [key, value] of Object.entries(loadEnv(mode, process.cwd(), "VITE_"))) {
    define[`import.meta.env.${key}`] = JSON.stringify(value);
  }

  return {
    plugins,
    define,
    resolve: {
      tsconfigPaths: true,
      alias: { "@": path.resolve(process.cwd(), "src") },
      dedupe: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime", "@tanstack/react-query", "@tanstack/query-core"],
    },
    optimizeDeps: {
      include: ["react", "react-dom", "react-dom/client", "react/jsx-runtime", "react/jsx-dev-runtime"],
    },
  };
});
