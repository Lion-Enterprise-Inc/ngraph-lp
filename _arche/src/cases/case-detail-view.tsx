"use client";

import { LocaleLink as Link } from "@/lib/i18n/locale-link";
import { ArrowLeft, TrendingUp } from "lucide-react";
import { CrossNav } from "@/app/(teles)/mr-otora/_components/cross-nav";
import { ScoreBandLabel, type ScoreBandKind } from "@/app/(teles)/mr-otora/cases/_components/score-band-label";
import { EXCELLENT_LINE, SURVIVAL_LINE, getAgeBadge, getBonus, getCombinedScore } from "@/lib/case-studies-data";
import type { CaseStudy } from "@/lib/case-studies-data";
import { useLocale } from "@/lib/i18n/context";
import { countryName } from "./country";

const TIER_LABEL_I18N: Record<string, { ja: string; en: string }> = {
  startup: { ja: "スタートアップ", en: "Startup" },
  fail: { ja: "失敗", en: "Failed" },
  japan: { ja: "日本企業", en: "Japanese Company" },
  social: { ja: "ソーシャル", en: "Social" },
  bronze: { ja: "100年+ レジェンド", en: "100yr+ Legend" },
  silver: { ja: "300年+ レジェンド", en: "300yr+ Legend" },
  gold: { ja: "500年+ レジェンド", en: "500yr+ Legend" },
  god: { ja: "W5", en: "W5" },
  earth: { ja: "アース20", en: "Earth 20" },
  craft: { ja: "クラフト", en: "Craft" },
};

const AGE_BADGE_I18N: Record<"bronze" | "silver" | "gold", { ja: string; en: string; emoji: string }> = {
  bronze: { ja: "100年+ レジェンド", en: "100yr+ Legend", emoji: "" },
  silver: { ja: "300年+ レジェンド", en: "300yr+ Legend", emoji: "" },
  gold: { ja: "500年+ レジェンド", en: "500yr+ Legend", emoji: "" },
};

const SCORE_LABEL_I18N: Record<string, { ja: string; en: string }> = {
  market: { ja: "ターゲット市場", en: "Market" },
  problem: { ja: "課題の実在性", en: "Problem" },
  solution: { ja: "ソリューション", en: "Solution" },
  team: { ja: "チーム", en: "Team" },
  traction: { ja: "トラクション", en: "Traction" },
  moat: { ja: "参入障壁", en: "Moat" },
  revenue: { ja: "収益モデル", en: "Revenue" },
  financial: { ja: "財務計画", en: "Financial" },
  efficiency: { ja: "資本効率", en: "Efficiency" },
  exit: { ja: "出口戦略", en: "Exit" },
  timing: { ja: "タイミング", en: "Timing" },
  insight: { ja: "独自の洞察", en: "Insight" },
};

const SCORE_ORDER: (keyof CaseStudy["scores"])[] = [
  "market", "problem", "solution", "team", "traction", "moat",
  "revenue", "financial", "efficiency", "exit", "timing", "insight",
];

const UI_I18N = {
  backToList: { ja: "ケース一覧に戻る", en: "Back to case list" },
  foundedPrefix: { ja: "創業", en: "Founded" },
  foundedSuffix: { ja: "年", en: "" },
  scoreSuffix: { ja: "/100 点", en: "/100" },
  situation: { ja: "当時の状況", en: "The Setting" },
  twelveScore: { ja: "12項目スコア", en: "12-Point Score" },
  threeAxes: { ja: "3軸評価", en: "3-Axis Evaluation" },
  axisSociety: { ja: "世間", en: "Society" },
  axisCustomer: { ja: "相手", en: "Customer" },
  axisSelf: { ja: "自己", en: "Self" },
  bonus: { ja: "ボーナス加点", en: "Bonus Points" },
  commentary: { ja: "テレスの所感", en: "Teles's Commentary" },
  keyToSurvival: { ja: "存続の鍵", en: "Key to Survival" },
  failCore: { ja: "失敗の核心", en: "Why It Failed" },
  otherCases: { ja: "他のケースを見る", en: "See other cases" },
  // 数は CASE_STUDIES.length から動的に補完（下の usage 側で interpolate）
  allCasesLink: { ja: "全ケース一覧へ", en: "View all cases" },
} as const;

function pick(field: { ja: string; en: string }, locale: string): string {
  return locale === "en" ? field.en : field.ja;
}

function pickLocalized(ja: string | undefined, en: string | undefined, locale: string): string {
  if (locale === "en" && en && en.trim().length > 0) return en;
  return ja ?? "";
}

function ScoreRow({ label, value, reason, max = 5 }: { label: string; value: number; reason?: string; max?: number }) {
  const pct = (value / max) * 100;
  const tone = value >= 4 ? "bg-(--c-ex)" : value >= 3 ? "bg-(--c-mean)" : value >= 2 ? "bg-(--c-weak)" : "bg-(--c-fail)";
  return (
    <div className="py-3 border-b border-border/70 last:border-b-0">
      <div className="flex items-center gap-3">
        <span className="w-[7.5em] shrink-0 text-sm font-bold text-foreground">{label}</span>
        <div className="flex-1 h-2 rounded-full bg-muted">
          <div className={`h-2 rounded-full ${tone}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="w-9 shrink-0 text-right text-sm font-bold tabular-nums text-foreground">{value}/{max}</span>
      </div>
      {reason && <p className="mt-1.5 text-sm leading-[1.8] text-muted-foreground">{reason}</p>}
    </div>
  );
}

export function CaseDetailView({ c }: { c: CaseStudy }) {
  const { locale } = useLocale();
  const total = getCombinedScore(c);
  const bonus = getBonus(c, locale);
  const axesTotal = (c.axes.society + c.axes.customer + c.axes.self) * 2;
  const tierLabel = pick(TIER_LABEL_I18N[c.tier] ?? { ja: c.tier, en: c.tier }, locale);
  const ageBadge = getAgeBadge(c);
  const isFail = c.tier === "fail";
  const survivalKey = pickLocalized(c.survivalKey, c.survivalKeyEn, locale);
  const failReason = pickLocalized(c.failReason, c.failReasonEn, locale);
  const showSurvival = !isFail && survivalKey && !survivalKey.includes("上記スコア参照");
  const showFail = isFail && failReason && !failReason.includes("上記スコア参照");
  const scoreBandKind: ScoreBandKind = isFail
    ? "deviation"
    : total >= EXCELLENT_LINE
      ? "excellence"
      : total >= SURVIVAL_LINE
        ? "mean"
        : "fragile";

  const displayName = locale === "en" && c.nameEn ? c.nameEn : c.name;
  const subName = locale === "en" ? null : (c.nameEn && c.nameEn !== c.name ? c.nameEn : null);
  const situation = pickLocalized(c.situation, c.situationEn, locale);
  const insight = pickLocalized(c.insight, c.insightEn, locale);
  const otoraComment = pickLocalized(c.otoraComment, c.otoraCommentEn, locale);
  const virtue = pickLocalized(c.virtue, c.virtueEn, locale);
  const localizedTierLabel = pickLocalized(c.tierLabel, c.tierLabelEn, locale);

  return (
    <div className="mx-auto w-full max-w-3xl px-4 sm:px-6 py-8 sm:py-12">
      <div className="mb-4">
        <Link
          href="/cases"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {pick(UI_I18N.backToList, locale)}
        </Link>
      </div>

      <header
        className="relative overflow-hidden rounded-2xl"
        style={{
          backgroundImage: `linear-gradient(135deg, ${c.color} 0%, ${c.color}cc 65%, rgba(0,0,0,0.25) 100%)`,
          backgroundColor: c.color,
        }}
      >
        <div className="px-4 sm:px-7 py-4 sm:py-8 text-white drop-shadow-sm">
          <div className="grid grid-cols-[auto_1fr_auto] gap-x-3 sm:gap-x-4 gap-y-1 items-start">
            <div className="flex h-12 w-12 sm:h-16 sm:w-16 shrink-0 items-center justify-center rounded-xl sm:rounded-2xl bg-white/20 backdrop-blur text-xl sm:text-2xl font-black">
              {c.initial}
            </div>
            <div className="min-w-0 self-center">
              <div className="flex flex-wrap items-center gap-x-1 gap-y-0.5 text-xs sm:text-xs font-medium text-white/85 leading-tight">
                <span className="whitespace-nowrap">{tierLabel}</span>
                {ageBadge && (
                  <span className="whitespace-nowrap">
                    <span className="opacity-70">｜</span>
                    {pick(AGE_BADGE_I18N[ageBadge], locale)}
                  </span>
                )}
                {localizedTierLabel && (
                  <span className="whitespace-nowrap opacity-70">｜{localizedTierLabel}</span>
                )}
              </div>
            </div>
            <div className="text-right shrink-0 row-span-2">
              <div className="text-xs tracking-widest uppercase text-white/80 leading-none">NCG</div>
              <div className="text-3xl sm:text-5xl font-black leading-none mt-1">{total}</div>
              <div className="text-xs text-white/75 mt-1">{pick(UI_I18N.scoreSuffix, locale)}</div>
              <div className="text-xs text-white/85 mt-0.5 whitespace-nowrap">
                <ScoreBandLabel kind={scoreBandKind} />
              </div>
            </div>
            <div className="col-span-2 min-w-0">
              <h1 className="text-xl sm:text-3xl font-black tracking-tight leading-tight break-words">
                                {displayName}
              </h1>
              {subName && (
                <p className="text-xs text-white/75 mt-1 font-mono tracking-wide break-words">{subName}</p>
              )}
              <p className="text-sm text-white/90 mt-1.5">
                {countryName(c.flag) && `${countryName(c.flag)}・`}
                {locale === "en"
                  ? `${pick(UI_I18N.foundedPrefix, locale)} ${c.year}`
                  : `${pick(UI_I18N.foundedPrefix, locale)} ${c.year}${pick(UI_I18N.foundedSuffix, locale)}`}
              </p>
            </div>
          </div>
          {insight && (
            <div className="mt-4 sm:mt-5 rounded-lg bg-black/25 backdrop-blur-sm px-3.5 py-2.5 border border-white/15">
              <p className="text-[15px] text-white leading-[1.7] font-bold">{insight}</p>
            </div>
          )}
        </div>
      </header>

      {situation && (
        <section className="mt-8">
          <h2 className="k-h text-foreground">{pick(UI_I18N.situation, locale)}</h2>
          <p className="k-body text-foreground whitespace-pre-wrap">{situation}</p>
        </section>
      )}

      <section className="mt-8">
        <h2 className="k-h text-foreground flex items-center gap-1.5">
          <TrendingUp className="h-3.5 w-3.5" />
          {pick(UI_I18N.twelveScore, locale)}{locale === "en" ? ` (${c.total}/60)` : `（${c.total}/60）`}
        </h2>
        <div className="rounded-xl border border-border/60 bg-card/60 p-4">
          {SCORE_ORDER.map((key) => (
            <ScoreRow
              key={key}
              label={pick(SCORE_LABEL_I18N[key], locale)}
              value={c.scores[key]}
              reason={c.reasons?.[key]}
            />
          ))}
        </div>
      </section>

      <section className="mt-6">
        <h2 className="k-h text-foreground">
          {pick(UI_I18N.threeAxes, locale)}{locale === "en" ? ` (${axesTotal}/30)` : `（${axesTotal}/30）`}
        </h2>
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: pick(UI_I18N.axisSociety, locale), value: c.axes.society * 2, tone: "border-(--c-society)/30 bg-(--c-society)/5 text-(--c-society)" },
            { label: pick(UI_I18N.axisCustomer, locale), value: c.axes.customer * 2, tone: "border-(--c-customer)/30 bg-(--c-customer)/5 text-(--c-customer)" },
            { label: pick(UI_I18N.axisSelf, locale), value: c.axes.self * 2, tone: "border-(--c-weak)/30 bg-(--c-weak)/5 text-(--c-weak)" },
          ].map((a) => (
            <div key={a.label} className={`rounded-xl border p-3 text-center ${a.tone}`}>
              <p className="text-sm font-bold">{a.label}</p>
              <p className="text-2xl font-black mt-1 text-foreground">
                {a.value}<span className="text-xs text-foreground/40 font-normal">/10</span>
              </p>
            </div>
          ))}
        </div>
      </section>

      {bonus.value > 0 && bonus.reason && (
        <section className="mt-6">
          <h2 className="k-h text-(--c-weak)">{pick(UI_I18N.bonus, locale)}</h2>
          <div className="rounded-xl border border-(--c-weak)/30 bg-(--c-weak)/5 p-3 flex items-baseline gap-3">
            <div className="text-3xl font-black text-(--c-weak) shrink-0 leading-none">+{bonus.value}</div>
            <p className="text-sm text-foreground leading-[1.8]">{bonus.reason}</p>
          </div>
        </section>
      )}

      {otoraComment && (
        <section className="mt-6">
          <h2 className="k-h text-foreground">
            {pick(UI_I18N.commentary, locale)}
          </h2>
          <div className="rounded-xl border border-border/60 bg-muted/40 p-4">
            <p className="k-body text-foreground whitespace-pre-wrap">{otoraComment}</p>
            {virtue && (
              <blockquote className="mt-3 border-l-[3px] border-primary/60 pl-3 py-0.5 text-foreground font-bold text-[15px] [font-family:var(--font-serif)]">
                {virtue}
              </blockquote>
            )}
          </div>
        </section>
      )}

      {(showSurvival || showFail) && (
        <section className="mt-6">
          <h2 className={`k-h ${showFail ? "text-(--c-fail)" : "text-(--c-ex)"}`}>
            {showFail ? pick(UI_I18N.failCore, locale) : pick(UI_I18N.keyToSurvival, locale)}
          </h2>
          <div className={`rounded-xl border p-4 ${showFail ? "bg-(--c-fail)/5 border-(--c-fail)/30" : "bg-(--c-ex)/5 border-(--c-ex)/30"}`}>
            <p className="k-body text-foreground whitespace-pre-wrap">
              {showFail ? failReason : survivalKey}
            </p>
          </div>
        </section>
      )}

      <section className="mt-10 pt-6 border-t border-border/40">
        <p className="text-sm font-semibold mb-4">{pick(UI_I18N.otherCases, locale)}</p>
        <Link
          href="/cases"
          className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
        >
          {pick(UI_I18N.allCasesLink, locale)}
          <ArrowLeft className="h-3.5 w-3.5 rotate-180" />
        </Link>
      </section>

      <CrossNav current="/cases" />
    </div>
  );
}
