"use client";

import { LocaleLink as Link } from "@/lib/i18n/locale-link";
import { ArrowLeft } from "lucide-react";
import type { CaseStudy } from "@/lib/case-studies-data";
import { useLocale } from "@/lib/i18n/context";
import { CardContent } from "./cases-page";
import { NgraphCta } from "./ngraph-cta";

/** 各社の詳細ページ（/cases/<slug>/）。中身は一覧のモーダルと同じ CardContent を使う。 */
export function CaseDetailView({ c }: { c: CaseStudy }) {
  const { locale } = useLocale();
  const ja = locale === "ja";

  return (
    <div className="mx-auto w-full max-w-5xl px-4 sm:px-6 py-8 sm:py-12">
      <div className="mb-4">
        <Link
          href="/cases"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {ja ? "ケース一覧に戻る" : "Back to case list"}
        </Link>
      </div>

      <article className="overflow-hidden rounded-2xl border border-border/60 bg-background">
        <CardContent c={c} isLoggedIn={false} locale={locale} rounded="" />
      </article>

      <section className="mt-10 pt-6 border-t border-border/40">
        <p className="text-sm font-semibold mb-4">{ja ? "他のケースを見る" : "See other cases"}</p>
        <Link
          href="/cases"
          className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
        >
          {ja ? "全ケース一覧へ" : "View all cases"}
          <ArrowLeft className="h-3.5 w-3.5 rotate-180" />
        </Link>
      </section>

      <div className="mt-10"><NgraphCta /></div>
    </div>
  );
}
