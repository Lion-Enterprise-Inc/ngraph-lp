import type { ReactNode } from "react";
// nicomachos のパスを ngraph.jp のパスへ。対話（/signup）は ngraph.jp に無いので出さない
const HIDE = ["/signup", "/login"];
function map(href: string): string {
  if (href === "/") return "/";
  if (href === "/cases") return "/cases/";
  if (href.startsWith("/cases/")) return href.endsWith("/") ? href : `${href}/`;
  return href;
}
export function LocaleLink({ href, children, className, ...rest }: { href: string; children?: ReactNode; className?: string; [k: string]: unknown }) {
  if (HIDE.includes(href)) return null;
  return <a href={map(href)} className={className} {...(rest as object)}>{children}</a>;
}
export default LocaleLink;
