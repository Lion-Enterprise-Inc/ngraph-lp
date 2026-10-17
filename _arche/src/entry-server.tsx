import { renderToString } from "react-dom/server";
import { App, type PageProps } from "./app";
import { CASE_STUDIES, slugifyCase, findCaseBySlug, getCombinedScore } from "./orig/case-studies-data";

export function render(props: PageProps): string {
  return renderToString(<App {...props} />);
}

// 詳細ページを作るスラグ。元データは同名同年の2件が同じスラグになることがあり、
// 元のサイトでも先に見つかる1件だけが開ける。同じ扱いにする。
export function slugs(): string[] {
  return [...new Set(CASE_STUDIES.map(slugifyCase))];
}

export function meta(slug: string) {
  const c = findCaseBySlug(slug)!;
  return { name: c.name, nameEn: c.nameEn ?? "", year: String(c.year), score: getCombinedScore(c), insight: c.insight ?? "" };
}

export const COUNT = CASE_STUDIES.length;
