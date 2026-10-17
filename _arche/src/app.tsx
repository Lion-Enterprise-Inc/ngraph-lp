import CasesPage from "./orig/cases-page";
import { CaseDetailView } from "./orig/case-detail-view";
import { findCaseBySlug } from "./orig/case-studies-data";

export type PageProps = { kind: "list" } | { kind: "detail"; slug: string };

// nicomachos.com の /cases と /cases/[slug] をそのまま描く（外側の枠だけ ngraph.jp 用）
export function App(props: PageProps) {
  if (props.kind === "list") return <CasesPage />;
  const c = findCaseBySlug(props.slug);
  if (!c) return null;
  return <CaseDetailView c={c} />;
}
