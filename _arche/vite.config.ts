import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

const r = (p: string) => fileURLToPath(new URL(p, import.meta.url));
// 元のソースの import 先を、ngraph.jp で動く差し替え（shims）か複写（orig）へ向ける
const alias = [
  { find: /^next\/image$/, replacement: r("./src/shims/image.tsx") },
  { find: /^next-auth\/react$/, replacement: r("./src/shims/next-auth.ts") },
  { find: /^@\/lib\/i18n\/locale-link$/, replacement: r("./src/shims/locale-link.tsx") },
  { find: /^@\/lib\/i18n\/context$/, replacement: r("./src/shims/i18n.tsx") },
  { find: /^@\/components\/ui\/button$/, replacement: r("./src/shims/button.tsx") },
  { find: /^@\/app\/\(teles\)\/mr-otora\/_components\/cross-nav$/, replacement: r("./src/shims/cross-nav.tsx") },
  { find: /^@\/app\/\(teles\)\/mr-otora\/_components\/judgment-foundation$/, replacement: r("./src/orig/judgment-foundation.tsx") },
  { find: /^@\/app\/\(teles\)\/mr-otora\/cases\/_components\/score-band-label$/, replacement: r("./src/orig/score-band-label.tsx") },
  { find: /^@\/lib\/case-studies-data$/, replacement: r("./src/orig/case-studies-data.ts") },
];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias },
  base: "/cases/_assets/",
  build: {
    outDir: "dist/client",
    emptyOutDir: true,
    assetsDir: "",
    rollupOptions: { input: { arche: r("./src/entry-client.tsx") } },
  },
});
