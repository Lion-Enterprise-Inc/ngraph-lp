"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { ArrowLeft, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, TrendingUp, MessageCircle, ArrowUp, Loader2, X, LayoutGrid, Table2, Map as MapIcon } from "lucide-react";
import Image from "next/image";
import { LocaleLink as Link } from "@/lib/i18n/locale-link";
import { useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { CrossNav } from "@/app/(teles)/mr-otora/_components/cross-nav";
import { JudgmentFoundation } from "@/app/(teles)/mr-otora/_components/judgment-foundation";
import { useLocale } from "@/lib/i18n/context";
import { CASE_STUDIES, SURVIVAL_LINE, EXCELLENT_LINE, getCombinedScore, getBonus, matchesFilter, getAgeBadge, getCanonicalCases, getEraGroupCases } from "@/lib/case-studies-data";
import type { CaseStudy, CaseScore, CaseReasons } from "@/lib/case-studies-data";
import { countryName } from "./country";
import { NgraphCta } from "./ngraph-cta";

/** Select English text when available and locale is 'en', otherwise fall back to Japanese. */
function pickLocalized(ja: string | undefined, en: string | undefined, locale: string): string {
  if (locale === "en" && en && en.trim().length > 0) return en;
  return ja ?? "";
}

function pickLocalizedReasons(reasons: CaseReasons, reasonsEn: CaseReasons | undefined, locale: string): CaseReasons {
  if (locale !== "en" || !reasonsEn) return reasons;
  const out = { ...reasons };
  (Object.keys(out) as (keyof CaseReasons)[]).forEach((k) => {
    const en = reasonsEn[k];
    if (en && en.trim().length > 0) out[k] = en;
  });
  return out;
}

const SCORE_LABELS_I18N: Record<string, { ja: string; en: string }> = {
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

const TIER_CONFIG_I18N: Record<string, { ja: string; en: string; emoji: string }> = {
  startup: { ja: "スタートアップ", en: "Startup", emoji: "" },
  fail: { ja: "失敗", en: "Failed", emoji: "" },
  japan: { ja: "日本企業", en: "Japan", emoji: "" },
  social: { ja: "ソーシャル", en: "Social", emoji: "" },
  bronze: { ja: "100年+ レジェンド", en: "100yr+ Legend", emoji: "" },
  silver: { ja: "300年+ レジェンド", en: "300yr+ Legend", emoji: "" },
  gold: { ja: "500年+ レジェンド", en: "500yr+ Legend", emoji: "" },
  god: { ja: "W10", en: "W10", emoji: "" },
  earth: { ja: "アース30", en: "Earth 30", emoji: "" },
  craft: { ja: "クラフト", en: "Craft", emoji: "" },
};

function ScoreBar({ value, max = 5 }: { value: number; max?: number }) {
  const pct = (value / max) * 100;
  const color = value >= 4 ? "bg-(--c-ex)" : value >= 3 ? "bg-(--c-mean)" : value >= 2 ? "bg-(--c-weak)" : "bg-(--c-fail)";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-muted/60 rounded-full">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono w-4 text-right opacity-70">{value}</span>
    </div>
  );
}

/* ── レーダーチャート ── */
const RADAR_KEYS = ["market", "problem", "solution", "team", "traction", "moat", "revenue", "financial", "efficiency", "exit", "timing", "insight"] as const;
const RADAR_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"];

function RadarChart({
  scores,
  size = 120,
  showLabels = false,
  color = "#2e6e4e",
  labelColor,
  gridColor,
  labelSize = 9,
}: {
  scores: CaseScore;
  size?: number;
  showLabels?: boolean;
  color?: string;
  labelColor?: string;
  gridColor?: string;
  labelSize?: number;
}) {
  const cx = size / 2;
  const cy = size / 2;
  const r = (size / 2) - (showLabels ? 14 : 8);
  const n = RADAR_KEYS.length;

  const toXY = (i: number, val: number) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const dist = (val / 5) * r;
    return { x: Math.round((cx + dist * Math.cos(angle)) * 100) / 100, y: Math.round((cy + dist * Math.sin(angle)) * 100) / 100 };
  };

  // グリッド線
  const gridLines = [1, 2, 3, 4, 5].map((level) => {
    const pts = Array.from({ length: n }, (_, i) => {
      const p = toXY(i, level);
      return `${p.x},${p.y}`;
    }).join(" ");
    return gridColor
      ? <polygon key={level} points={pts} fill="none" stroke={gridColor} strokeWidth={level === 5 ? 0.6 : 0.3} />
      : <polygon key={level} points={pts} fill="none" stroke="currentColor" strokeWidth={level === 5 ? 0.5 : 0.3} className="text-foreground/10" />;
  });

  // 軸線
  const axes = Array.from({ length: n }, (_, i) => {
    const p = toXY(i, 5);
    return gridColor
      ? <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke={gridColor} strokeWidth={0.3} />
      : <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="currentColor" strokeWidth={0.3} className="text-foreground/10" />;
  });

  // データ
  const dataPts = RADAR_KEYS.map((k, i) => toXY(i, scores[k] || 0));
  const dataPath = dataPts.map((p) => `${p.x},${p.y}`).join(" ");

  // ラベル（A〜L）
  const labels = showLabels ? RADAR_KEYS.map((_, i) => {
    const p = toXY(i, 5.7);
    return (
      <text key={i} x={p.x} y={p.y} textAnchor="middle" dominantBaseline="central"
        fill={labelColor ?? "currentColor"}
        className={labelColor ? undefined : "fill-muted-foreground"}
        style={{ fontSize: `${labelSize}px`, fontWeight: 600, letterSpacing: "0.05em" }}>
        {RADAR_LETTERS[i]}
      </text>
    );
  }) : null;

  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${size} ${size}`} preserveAspectRatio="xMidYMid meet" overflow="visible">
      {gridLines}
      {axes}
      <polygon points={dataPath} fill={color} fillOpacity={0.2} stroke={color} strokeWidth={1.5} />
      {dataPts.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={1.5} fill={color} />
      ))}
      {labels}
    </svg>
  );
}

/* ── 12項目スコアグリッド（タップ展開） ── */
const SCORE_SHORT: Record<string, { ja: string; en: string }> = {
  market: { ja: "市場", en: "Market" },
  problem: { ja: "課題", en: "Problem" },
  solution: { ja: "解決策", en: "Solution" },
  team: { ja: "チーム", en: "Team" },
  traction: { ja: "実績", en: "Traction" },
  moat: { ja: "障壁", en: "Moat" },
  revenue: { ja: "収益", en: "Revenue" },
  financial: { ja: "財務", en: "Finance" },
  efficiency: { ja: "効率", en: "Efficiency" },
  exit: { ja: "出口", en: "Exit" },
  timing: { ja: "時機", en: "Timing" },
  insight: { ja: "洞察", en: "Insight" },
};

function ScoreGrid({ scores, reasons, locale }: {
  scores: CaseScore;
  reasons: CaseStudy["reasons"];
  locale: string;
}) {
  const ja = locale === "ja";
  const L = (key: string) => SCORE_LABELS_I18N[key]?.[locale as "ja" | "en"] || key;
  const name = (k: (typeof RADAR_KEYS)[number]) => `${RADAR_LETTERS[RADAR_KEYS.indexOf(k)]} ${L(k)}`;
  const strong = RADAR_KEYS.filter((k) => scores[k] >= 5);
  const weak = RADAR_KEYS.filter((k) => scores[k] <= 2);
  return (
    <div>
      {(strong.length > 0 || weak.length > 0) && (
        <div className="mb-4 grid gap-1 text-sm sm:grid-cols-2">
          {strong.length > 0 && (
            <p><span className="mr-2 font-bold text-(--c-ex)">{ja ? "強み" : "Strengths"}</span>{strong.map(name).join(ja ? "・" : ", ")}</p>
          )}
          {weak.length > 0 && (
            <p><span className="mr-2 font-bold text-(--c-weak)">{ja ? "弱み" : "Weaknesses"}</span>{weak.map(name).join(ja ? "・" : ", ")}</p>
          )}
        </div>
      )}
      <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
        {RADAR_KEYS.map((key, i) => {
          const val = scores[key];
          const edge = val >= 5 ? "border-(--c-ex)" : val <= 2 ? "border-(--c-weak)" : "border-border";
          return (
            <div key={key} className={`border-l-2 pl-3 ${edge}`}>
              <div className="flex items-baseline gap-1.5">
                <span className="w-3.5 shrink-0 text-xs font-bold text-primary">{RADAR_LETTERS[i]}</span>
                <span className="text-sm font-bold text-foreground">{L(key)}</span>
                <span className="ml-auto text-sm font-bold tabular-nums text-foreground">
                  {val}<span className="text-xs font-normal text-foreground/40">/5</span>
                </span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-muted">
                <div className={`h-2 rounded-full ${val >= 4 ? "bg-(--c-ex)" : val >= 3 ? "bg-(--c-mean)" : val >= 2 ? "bg-(--c-weak)" : "bg-(--c-fail)"}`} style={{ width: `${(val / 5) * 100}%` }} />
              </div>
              <p className="mt-1.5 text-sm leading-[1.75] text-muted-foreground">{reasons[key]}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── ヒーロー中央：3軸・存続/卓越ラインに対する位置・徳目 ── */
function HeroSummary({ axes, score, virtue, ja }: {
  axes: CaseStudy["axes"];
  score: number;
  virtue: string;
  ja: boolean;
}) {
  const pos = Math.max(0, Math.min(100, score));
  const verdict = score >= EXCELLENT_LINE
    ? (ja ? `卓越ライン（${EXCELLENT_LINE}）を ${score - EXCELLENT_LINE} 点上回る` : `${score - EXCELLENT_LINE} above the excellence line`)
    : score >= SURVIVAL_LINE
      ? (ja ? `存続ライン（${SURVIVAL_LINE}）を ${score - SURVIVAL_LINE} 点上回る` : `${score - SURVIVAL_LINE} above the survival line`)
      : (ja ? `存続ライン（${SURVIVAL_LINE}）まで ${SURVIVAL_LINE - score} 点足りない` : `${SURVIVAL_LINE - score} below the survival line`);
  const items = [
    { label: ja ? "世間" : "Society", value: axes.society * 2 },
    { label: ja ? "相手" : "Customer", value: axes.customer * 2 },
    { label: ja ? "自己" : "Self", value: axes.self * 2 },
  ];
  return (
    <div className="space-y-3">
      <div className="flex gap-6">
        {items.map((a) => (
          <div key={a.label}>
            <p className="text-xs text-white/75">{a.label}</p>
            <p className="text-xl font-black leading-tight">
              {a.value}<span className="text-xs font-normal text-white/65">/10</span>
            </p>
          </div>
        ))}
      </div>
      <div>
        <p className="mb-1.5 text-xs text-white/90">{verdict}</p>
        <div className="relative h-1.5 rounded-full bg-white/25">
          <div className="absolute inset-y-0 left-0 rounded-full bg-white/85" style={{ width: `${pos}%` }} />
          {[SURVIVAL_LINE, EXCELLENT_LINE].map((v) => (
            <span key={v} className="absolute -top-1 h-3.5 w-px bg-white" style={{ left: `${v}%` }} />
          ))}
        </div>
        <div className="relative mt-1 h-4 text-xs text-white/75">
          <span className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: `${SURVIVAL_LINE}%` }}>{ja ? "存続" : "Survival"} {SURVIVAL_LINE}</span>
          <span className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: `${EXCELLENT_LINE}%` }}>{ja ? "卓越" : "Excellence"} {EXCELLENT_LINE}</span>
        </div>
      </div>
      {virtue && (
        <span className="inline-block rounded-md bg-white/15 px-2 py-0.5 text-xs font-bold">{virtue}</span>
      )}
    </div>
  );
}

/* ── NCG の内訳（12項目＋3軸＋加点） ── */
function ScoreBreakdown({ total, axesTotal, bonus, score, ja }: {
  total: number;
  axesTotal: number;
  bonus: { value: number; reason: string };
  score: number;
  ja: boolean;
}) {
  const parts = [
    { label: ja ? "12項目" : "12 criteria", value: `${total}`, max: "/60" },
    { label: ja ? "3軸" : "3 axes", value: `${axesTotal}`, max: "/30" },
    ...(bonus.value > 0 ? [{ label: ja ? "加点" : "Bonus", value: `+${bonus.value}`, max: "" }] : []),
  ];
  return (
    <section className="rounded-xl border border-border/60 bg-muted/40 px-4 py-3">
      <div className="flex flex-wrap items-end gap-x-3 gap-y-2">
        {parts.map((p, i) => (
          <div key={p.label} className="flex items-end gap-3">
            {i > 0 && <span className="pb-1 text-foreground/40">＋</span>}
            <div>
              <p className="text-xs font-bold text-muted-foreground">{p.label}</p>
              <p className="text-xl font-black leading-tight text-foreground">
                {p.value}<span className="text-xs font-normal text-foreground/40">{p.max}</span>
              </p>
            </div>
          </div>
        ))}
        <span className="pb-1 text-foreground/40">＝</span>
        <div>
          <p className="text-xs font-bold text-muted-foreground">NCG</p>
          <p className="text-xl font-black leading-tight text-foreground">
            {score}<span className="text-xs font-normal text-foreground/40">/100</span>
          </p>
        </div>
      </div>
      {bonus.value > 0 && bonus.reason && (
        <p className="mt-2 text-sm leading-[1.75] text-muted-foreground">{ja ? "加点の理由：" : "Bonus: "}{bonus.reason}</p>
      )}
    </section>
  );
}

/* ── 3軸 三角チャート ── */
function TriangleChart({ axes, size = 64, color = "#2e6e4e", showLabels = false, locale = "ja" }: {
  axes: { society: number; customer: number; self: number };
  size?: number;
  color?: string;
  showLabels?: boolean;
  locale?: "ja" | "en";
}) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - (showLabels ? 10 : 4);
  // 3頂点: 上(society)、右下(customer)、左下(self)
  const toXY = (i: number, val: number) => {
    const angle = (Math.PI * 2 * i) / 3 - Math.PI / 2;
    const dist = (val / 5) * r;
    return { x: Math.round((cx + dist * Math.cos(angle)) * 100) / 100, y: Math.round((cy + dist * Math.sin(angle)) * 100) / 100 };
  };
  const grid = [1, 2, 3, 4, 5].map((level) => {
    const pts = [0, 1, 2].map((i) => toXY(i, level));
    return <polygon key={level} points={pts.map(p => `${p.x},${p.y}`).join(" ")} fill="none" stroke="currentColor" strokeWidth={level === 5 ? 0.5 : 0.3} className="text-foreground/10" />;
  });
  const dataPts = [0, 1, 2].map((i) => toXY(i, [axes.society, axes.customer, axes.self][i]));
  const shouldShowLabels = showLabels || size >= 100;
  const labels = shouldShowLabels
    ? (locale === "ja" ? ["世間", "相手", "自己"] : ["Society", "Customer", "Self"])
    : null;
  const labelFontSize = size >= 100 ? 10 : 9;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} overflow="visible">
      {grid}
      {[0, 1, 2].map((i) => {
        const p = toXY(i, 5);
        return <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="currentColor" strokeWidth={0.3} className="text-foreground/10" />;
      })}
      <polygon points={dataPts.map(p => `${p.x},${p.y}`).join(" ")} fill={color} fillOpacity={0.25} stroke={color} strokeWidth={1.5} />
      {dataPts.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r={1.5} fill={color} />)}
      {labels && [0, 1, 2].map((i) => {
        const p = toXY(i, 6);
        return (
          <text key={i} x={p.x} y={p.y} textAnchor="middle" dominantBaseline="central"
            className="fill-current text-foreground/60" style={{ fontSize: `${labelFontSize}px`, fontWeight: 500 }}>
            {labels[i]}
          </text>
        );
      })}
    </svg>
  );
}

/* ── 分析手法（ピッチ診断と同じ採点基盤の要約） ── */
const METHOD_CRITERIA = [
  { key: "market", label: "ターゲット市場", labelEn: "Market", desc: "規模・成長率・定義の明確さ", descEn: "Size, growth, clarity of definition" },
  { key: "problem", label: "課題の実在性", labelEn: "Problem", desc: "持続的な痛み、顧客の声", descEn: "Sustained pain, customer voice" },
  { key: "solution", label: "ソリューション", labelEn: "Solution", desc: "既存比10倍の改善があるか", descEn: "10x improvement over existing" },
  { key: "team", label: "チーム", labelEn: "Team", desc: "実績・専門性・補完関係", descEn: "Track record, expertise, complementarity" },
  { key: "traction", label: "トラクション", labelEn: "Traction", desc: "有料顧客、LTV/CAC、NRR", descEn: "Paying customers, LTV/CAC, NRR" },
  { key: "moat", label: "参入障壁", labelEn: "Moat", desc: "ネットワーク効果・データ優位", descEn: "Network effects, data advantage" },
  { key: "revenue", label: "収益モデル", labelEn: "Revenue", desc: "ユニットエコノミクスの成立", descEn: "Sound unit economics" },
  { key: "financial", label: "財務計画", labelEn: "Financial", desc: "前提の透明性と現実性", descEn: "Assumption clarity & realism" },
  { key: "efficiency", label: "資本効率", labelEn: "Efficiency", desc: "バーンマルチプル", descEn: "Burn multiple" },
  { key: "exit", label: "出口戦略", labelEn: "Exit", desc: "M&A・IPOへの道筋", descEn: "Path to M&A / IPO" },
  { key: "timing", label: "タイミング", labelEn: "Timing", desc: "なぜ今か、市場の変化点", descEn: "Why now — market inflection" },
  { key: "insight", label: "独自の洞察", labelEn: "Insight", desc: "他者が知らない重要な真実", descEn: "Important truth others don't know" },
];

const METHOD_ETHICS_JA = [
  { term: "エウダイモニア", sub: "幸福", desc: "事業の目的は利益ではなく、関わる全員の「よく生きる」こと" },
  { term: "アレテー", sub: "卓越性", desc: "自分の役割を最高の形で果たすこと" },
  { term: "メソテース", sub: "中庸", desc: "極端を避け、状況に応じた最善を重ねる" },
  { term: "プロネーシス", sub: "実践知", desc: "この状況・この人にとっての最善を見極める知恵" },
  { term: "ヘクシス", sub: "習慣的性向", desc: "日々の判断の積み重ねが事業の性格を作る" },
  { term: "フィリア", sub: "友愛", desc: "取引先・従業員・顧客との信頼関係こそ最大の資産" },
];

const METHOD_ETHICS_EN = [
  { term: "Eudaimonia", sub: "Flourishing", desc: "Business aims at the flourishing of everyone involved." },
  { term: "Arete", sub: "Excellence", desc: "Fulfill your role at its highest form." },
  { term: "Mesotes", sub: "The Mean", desc: "Avoid extremes; layer the best choice for the situation." },
  { term: "Phronesis", sub: "Practical Wisdom", desc: "Wisdom to see what's best for THIS situation." },
  { term: "Hexis", sub: "Habituated Disposition", desc: "Daily decisions shape the character of a business." },
  { term: "Philia", sub: "Friendship", desc: "Trust is your greatest asset." },
];

function MethodologySection({ locale }: { locale: string }) {
  const ja = locale === "ja";
  const [open, setOpen] = useState(false);
  const ethics = ja ? METHOD_ETHICS_JA : METHOD_ETHICS_EN;
  return (
    <div className="rounded-xl border border-border/60 bg-card/50 mt-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
        aria-expanded={open}
      >
        <div>
          <p className="text-base font-bold [font-family:var(--font-serif)]">{ja ? "この分析の方法論" : "Methodology"}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{ja ? "12項目 × 3軸 × ニコマコス倫理学" : "12 criteria × 3 axes × Nicomachean Ethics"}</p>
        </div>
        {open ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>
      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-border/40 pt-4">
          {/* 12項目 */}
          <div>
            <p className="text-xs font-semibold mb-2">{ja ? "12項目 × 5点 = 60点満点" : "12 criteria × 5 pts = 60 total"}</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {METHOD_CRITERIA.map((c) => (
                <div key={c.key} className="flex items-start gap-2 rounded-lg bg-muted/40 px-3 py-2">
                  <div className="w-1 self-stretch shrink-0 rounded-full bg-primary/30" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium">{ja ? c.label : c.labelEn}</p>
                    <p className="text-xs text-muted-foreground leading-snug">{ja ? c.desc : c.descEn}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* NCG 三方評価 */}
          <div>
            <p className="text-xs font-semibold mb-1">{ja ? "NCG（Nicomachos Company Graph）— 三方評価" : "NCG — 3-Axis Review"}</p>
            <p className="text-xs text-muted-foreground mb-2">{ja ? "12項目を3軸に集約。掛け算で総合力を算出" : "12 criteria aggregated into 3 axes, multiplied into one score"}</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <div className="rounded-lg border border-(--c-society)/20 bg-(--c-society)/5 p-3">
                <p className="text-xs font-semibold text-(--c-society) mb-1">{ja ? "世間（Society）" : "Society"}</p>
                <p className="text-xs text-muted-foreground leading-snug">{ja ? "タイミング・独自の洞察・出口戦略・社会貢献度" : "Timing, insight, exit, social contribution"}</p>
              </div>
              <div className="rounded-lg border border-(--c-customer)/20 bg-(--c-customer)/5 p-3">
                <p className="text-xs font-semibold text-(--c-customer) mb-1">{ja ? "相手（Customer）" : "Customer"}</p>
                <p className="text-xs text-muted-foreground leading-snug">{ja ? "市場規模・課題・ソリューション・トラクション" : "Market, problem, solution, traction"}</p>
              </div>
              <div className="rounded-lg border border-(--c-weak)/20 bg-(--c-weak)/5 p-3">
                <p className="text-xs font-semibold text-(--c-weak) mb-1">{ja ? "自己（Self）" : "Self"}</p>
                <p className="text-xs text-muted-foreground leading-snug">{ja ? "チーム・参入障壁・収益モデル・財務計画・資本効率" : "Team, moat, revenue, financials, efficiency"}</p>
              </div>
            </div>
          </div>

          {/* ニコマコス倫理学 */}
          <div>
            <p className="text-xs font-semibold mb-2">{ja ? "判断基盤 — ニコマコス倫理学" : "Judgment base — Nicomachean Ethics"}</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {ethics.map((item) => (
                <div key={item.term} className="rounded-lg bg-muted/40 p-2.5">
                  <p className="text-xs font-semibold">{item.term}</p>
                  <p className="text-xs text-primary/80 mb-1">{item.sub}</p>
                  <p className="text-xs text-foreground/90 leading-snug">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const TIER_BORDER: Record<string, string> = {
  startup: "border-border/40",
  fail: "border-(--c-fail)/30",
  japan: "border-border/40",
  bronze: "border-(--c-weak)/40",
  silver: "border-border",
  gold: "border-(--c-weak)/50",
  god: "border-(--c-weak)/60",
  earth: "border-(--c-mean)/40",
  craft: "border-(--c-weak)/50",
  social: "border-border/40",
};

const TIER_ACCENT: Record<string, string> = {
  startup: "",
  fail: "ring-1 ring-(--c-fail)/20",
  japan: "",
  bronze: "ring-1 ring-(--c-weak)/20",
  silver: "ring-1 ring-border",
  gold: "ring-1 ring-(--c-weak)/30",
  god: "ring-1 ring-(--c-weak)/30",
  earth: "ring-1 ring-(--c-mean)/20",
  craft: "ring-1 ring-(--c-weak)/30",
  social: "",
};

/* ── テレス対話パネル ── */
type ChatMsg = { role: "user" | "assistant"; content: string };

function OtoraChat({ caseName, context, onClose, locale, isFail }: { caseName: string; context: string; onClose: () => void; locale: string; isFail: boolean }) {
  const ja = locale === "ja";
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);
  useEffect(() => { inputRef.current?.focus(); }, []);

  const send = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;
    const enrichedText = msgs.length === 0
      ? (ja
          ? `以下の企業「${caseName}」の診断データを踏まえて、日本語で回答してください:\n\n${context}\n\n質問: ${text.trim()}`
          : `Based on the diagnostic data for "${caseName}" below, please answer in English:\n\n${context}\n\nQuestion: ${text.trim()}`)
      : (ja ? text.trim() : `Please answer in English: ${text.trim()}`);
    const userMsg: ChatMsg = { role: "user", content: text.trim() };
    setMsgs(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch("/api/chat-assistant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: enrichedText, history: msgs, mode: "chat", feature: "arche" }),
      });
      const data = await res.json();
      setMsgs(prev => [...prev, { role: "assistant", content: data.reply || data.error || (ja ? "エラー" : "Error") }]);
    } catch {
      setMsgs(prev => [...prev, { role: "assistant", content: ja ? "通信エラーが発生しました。" : "A network error occurred." }]);
    } finally { setLoading(false); }
  }, [msgs, loading, caseName, context, ja]);

  const presets = isFail
    ? (ja
        ? ["失敗の本当の原因は？", "事前に回避できた？", "学べる教訓は？"]
        : ["What was the real cause of the failure?", "Could it have been avoided?", "What's the lesson to take away?"])
    : (ja
        ? ["成功した最大の理由は？", "自分の事業に活かせる点は？", "弱点は？"]
        : ["What's the biggest reason they succeeded?", "What can I apply to my own business?", "What are the weaknesses?"]);

  return (
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/40" onClick={onClose}>
      <div className="w-full max-w-lg h-[70vh] sm:h-[500px] bg-card rounded-t-2xl sm:rounded-2xl border border-border shadow-2xl flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-border/60 shrink-0">
          <div className="flex items-center gap-2">
            <Image src="/teles.png" alt="Teles" width={16} height={16} />
            <span className="text-sm font-semibold">{ja ? "テレスに質問" : "Ask Teles"} — {caseName}</span>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted"><X className="h-4 w-4" /></button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
          {msgs.length === 0 && (
            <div className="text-center py-6">
              <p className="text-sm text-muted-foreground mb-3">{ja ? "何でも聞いてください" : "Ask anything"}</p>
              <div className="flex flex-wrap justify-center gap-1.5">
                {presets.map(q => (
                  <button key={q} onClick={() => send(q)} className="text-xs bg-muted px-3 py-1.5 rounded-full hover:bg-muted/80">{q}</button>
                ))}
              </div>
            </div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed ${m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
                {m.content}
              </div>
            </div>
          ))}
          {loading && <div className="flex justify-start"><div className="bg-muted rounded-xl px-3 py-2"><Loader2 className="h-4 w-4 animate-spin" /></div></div>}
          <div ref={endRef} />
        </div>
        <div className="px-3 py-2.5 border-t border-border/60 shrink-0">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
              placeholder={ja ? "質問を入力..." : "Type your question..."}
              rows={1}
              className="flex-1 resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring min-h-[36px] max-h-[80px]"
            />
            <Button size="sm" className="h-9 w-9 p-0 shrink-0" onClick={() => send(input)} disabled={!input.trim() || loading}>
              <ArrowUp className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── カード内容（スライダー内で使う） ── */
export function CardContent({ c, isLoggedIn, onChat, locale, rounded = "rounded-t-2xl" }: { c: CaseStudy; isLoggedIn: boolean; onChat?: () => void; locale: string; rounded?: string }) {
  const tierInfo = TIER_CONFIG_I18N[c.tier];
  const ageBadgeTier = getAgeBadge(c);
  const ageBadge = ageBadgeTier ? TIER_CONFIG_I18N[ageBadgeTier] : null;
  const isFail = c.tier === "fail";
  const ja = locale === "ja";
  const localizedSituation = pickLocalized(c.situation, c.situationEn, locale);
  const localizedInsight = pickLocalized(c.insight, c.insightEn, locale);
  const localizedOtoraComment = pickLocalized(c.otoraComment, c.otoraCommentEn, locale);
  const localizedVirtue = pickLocalized(c.virtue, c.virtueEn, locale);
  const localizedTierLabel = pickLocalized(c.tierLabel, c.tierLabelEn, locale);
  const localizedSurvivalKey = pickLocalized(c.survivalKey, c.survivalKeyEn, locale);
  const localizedFailReason = pickLocalized(c.failReason, c.failReasonEn, locale);
  const localizedReasons = pickLocalizedReasons(c.reasons, c.reasonsEn, locale);

  const score = getCombinedScore(c);
  const bonus = getBonus(c, locale);
  const axesTotal = (c.axes.society + c.axes.customer + c.axes.self) * 2;
  const showSurvival = !isFail && localizedSurvivalKey && !localizedSurvivalKey.includes("上記スコア参照");
  const showFail = isFail && localizedFailReason && !localizedFailReason.includes("上記スコア参照");
  const heroTextColor = isFail ? "text-white" : score >= EXCELLENT_LINE ? "text-white" : "text-white";
  const scoreAccent = isFail ? "text-white" : score >= EXCELLENT_LINE ? "text-white" : "text-white";

  return (
    <>
      {/* ヒーロー（NHGと同等のヘッダー密度） */}
      <div
        className={`relative overflow-hidden ${rounded}`}
        style={{
          backgroundImage: `linear-gradient(135deg, ${c.color} 0%, ${c.color}cc 65%, rgba(0,0,0,0.25) 100%)`,
          backgroundColor: c.color,
        }}
      >
        <div className={`relative px-4 sm:px-6 pt-4 sm:pt-6 pb-4 ${heroTextColor} drop-shadow-sm`}>
          {/*
            SP: 人物 NHG モーダル（sage-detail-modal）と同じコンパクト1行ヘッダー。
              [ロゴ 56px] [名前+ロケール名+バッジ+年 stacked, flex-1] [小レーダー 80px]
            PC: 既存の3カラム grid（左ロゴ・中央バッジ・右レーダー大、下段に名前）を維持。
          */}

          {/* SP */}
          <div className="sm:hidden flex items-start gap-3">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-white/20 backdrop-blur text-xl font-black text-white drop-shadow">
              {c.initial}
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-lg font-black tracking-tight leading-tight break-words">
                                {locale === "en" && c.nameEn ? c.nameEn : c.name}
              </h2>
              {locale !== "en" && c.nameEn && (
                <p className="text-xs text-white/70 mt-0.5 font-mono tracking-wide break-words">{c.nameEn}</p>
              )}
              <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 mt-1.5 text-xs text-white/85 leading-tight">
                {tierInfo.emoji && <span>{tierInfo.emoji}</span>}
                <span className="whitespace-nowrap">{tierInfo[locale as "ja" | "en"]}</span>
                {ageBadge && (
                  <>
                    <span className="opacity-50">·</span>
                    <span className="whitespace-nowrap">{ageBadge.emoji} {ageBadge[locale as "ja" | "en"]}</span>
                  </>
                )}
                {localizedTierLabel && (
                  <>
                    <span className="opacity-50">·</span>
                    <span className="whitespace-nowrap">{localizedTierLabel}</span>
                  </>
                )}
                <span className="opacity-50">·</span>
                <span className="whitespace-nowrap">{countryName(c.flag)}{countryName(c.flag) ? "・" : ""}{ja ? `${c.year}年` : c.year}</span>
              </div>
            </div>
            <div className="relative w-20 h-20 shrink-0 self-center">
              <div className="absolute inset-0 flex items-center justify-center">
                <RadarChart
                  scores={c.scores}
                  size={80}
                  showLabels={false}
                  color="rgba(255,255,255,0.9)"
                  gridColor="rgba(255,255,255,0.2)"
                />
              </div>
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
                <div className={`text-base font-black leading-none ${scoreAccent}`}>{score}</div>
                <div className="text-xs text-white/60 leading-none mt-0.5">/100</div>
              </div>
            </div>
          </div>

          {/* PC */}
          <div className="hidden sm:flex sm:items-center sm:gap-6">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-3">
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-white/20 backdrop-blur text-2xl font-black text-white drop-shadow">
                  {c.initial}
                </div>
                <div className="flex min-w-0 flex-wrap items-center gap-1 text-xs font-medium leading-tight text-white/85">
                  {tierInfo.emoji && <span>{tierInfo.emoji}</span>}
                  <span className="whitespace-nowrap">{tierInfo[locale as "ja" | "en"]}</span>
                  {ageBadge && (
                    <span className="whitespace-nowrap">
                      <span className="opacity-70">｜</span>
                      {ageBadge.emoji}{" "}
                      {ageBadge[locale as "ja" | "en"]}
                    </span>
                  )}
                  {localizedTierLabel && <span className="opacity-70 whitespace-nowrap">｜{localizedTierLabel}</span>}
                </div>
              </div>
              <h2 className="mt-3 text-2xl font-black tracking-tight leading-tight break-words">
                {locale === "en" && c.nameEn ? c.nameEn : c.name}
              </h2>
              {locale !== "en" && c.nameEn && c.nameEn !== c.name && (
                <p className="text-xs text-white/70 mt-0.5 font-mono tracking-wide break-words">{c.nameEn}</p>
              )}
              <p className="text-sm text-white/85 mt-1">{countryName(c.flag)}{countryName(c.flag) ? "・" : ""}{ja ? `創業 ${c.year}年` : `Founded ${c.year}`}</p>
            </div>
            <div className="hidden md:block w-[300px] shrink-0">
              <HeroSummary axes={c.axes} score={score} virtue={localizedVirtue} ja={ja} />
            </div>
            <div className="relative shrink-0 w-32 h-32">
              <div className="absolute inset-0 flex items-center justify-center">
                <RadarChart
                  scores={c.scores}
                  size={128}
                  showLabels
                  color="rgba(255,255,255,0.9)"
                  gridColor="rgba(255,255,255,0.2)"
                  labelColor="rgba(255,255,255,0.85)"
                  labelSize={9}
                />
              </div>
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
                <div className="text-xs text-white/80 tracking-widest uppercase leading-none">NCG</div>
                <div className={`text-3xl font-black leading-none mt-0.5 ${scoreAccent}`}>{score}</div>
                <div className="text-xs text-white/70 leading-none mt-0.5">/100</div>
              </div>
            </div>
          </div>

          {/* md 未満：要約は名前の下に */}
          <div className="md:hidden mt-4">
            <HeroSummary axes={c.axes} score={score} virtue={localizedVirtue} ja={ja} />
          </div>

          {/* 洞察バナー（ヒーロー下に浮かせる） */}
          {localizedInsight && (
            <div className="mt-4 rounded-lg bg-black/20 backdrop-blur-sm px-3 py-2 border border-white/15">
              <p className="text-[15px] text-white font-bold leading-[1.7]">{localizedInsight}</p>
            </div>
          )}
        </div>
      </div>

      {/* 本文 */}
      <div className="px-4 sm:px-6 py-5 sm:py-6 text-[15px] leading-[1.9] space-y-7">
        <div className="grid gap-7 lg:grid-cols-2 lg:gap-10">
          <div className="space-y-7">
            <ScoreBreakdown total={c.total} axesTotal={axesTotal} bonus={bonus} score={score} ja={ja} />
            <section>
              <h3 className="k-h text-foreground">
                {ja ? "当時の状況" : "Context"}
              </h3>
              <p className="text-foreground whitespace-pre-wrap">{localizedSituation}</p>
            </section>
          </div>
          <section>
            <h3 className="k-h text-foreground justify-between">
              <span className="flex items-center gap-1.5">
                <Image src="/teles.png" alt="Teles" width={12} height={12} />
                {ja ? "テレスの所感" : "Teles' Insight"}
              </span>
              {!onChat ? null : isLoggedIn ? (
                <button onClick={onChat} className="flex items-center gap-1 text-xs font-normal text-primary hover:underline">
                  <MessageCircle className="h-3 w-3" />{ja ? "対話" : "Chat"}
                </button>
              ) : (
                <Link href="/signup" className="flex items-center gap-1 text-xs font-normal text-primary hover:underline">
                  <MessageCircle className="h-3 w-3" />{ja ? "対話" : "Chat"}
                </Link>
              )}
            </h3>
            <p className="text-foreground whitespace-pre-wrap">{localizedOtoraComment}</p>
          </section>
        </div>

        {/* 存続の鍵 / 失敗の核心 */}
        {(showSurvival || showFail) && (
          <section>
            <h3 className={`k-h ${showFail ? "text-(--c-fail)" : "text-(--c-ex)"}`}>
              {showFail ? (ja ? "失敗の核心" : "Why it failed") : (ja ? "存続の鍵" : "Key to survival")}
            </h3>
            <div className={`rounded-xl p-3 border ${showFail ? "bg-(--c-fail)/5 border-(--c-fail)/30" : "bg-(--c-ex)/5 border-(--c-ex)/30"}`}>
              <p className="text-foreground whitespace-pre-wrap">{showFail ? localizedFailReason : localizedSurvivalKey}</p>
            </div>
          </section>
        )}

        {/* 12項目スコア（A〜L） */}
        <section>
          <h3 className="k-h text-foreground">
            <TrendingUp className="h-3.5 w-3.5" />
            {ja ? `12項目スコア（${c.total}/60）` : `12 Criteria (${c.total}/60)`}
          </h3>
          <ScoreGrid scores={c.scores} reasons={localizedReasons} locale={locale} />
        </section>
      </div>
    </>
  );
}

/* ── スライダーモーダル ── */
function SliderModal({ items, initialIdx, isLoggedIn, onClose, locale }: {
  items: CaseStudy[];
  initialIdx: number;
  isLoggedIn: boolean;
  onClose: () => void;
  locale: string;
}) {
  const [idx, setIdx] = useState(initialIdx);
  const [chatCase, setChatCase] = useState<CaseStudy | null>(null);
  const [direction, setDirection] = useState<"left" | "right" | null>(null);
  // eraGroup を持つ entry のとき、モーダル内で時系列タブで切り替えたい時の上書き state
  const [eraOverride, setEraOverride] = useState<CaseStudy | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);

  const go = useCallback((dir: "left" | "right") => {
    const next = dir === "right" ? idx + 1 : idx - 1;
    if (next < 0 || next >= items.length) return;
    setDirection(dir);
    setTimeout(() => {
      setIdx(next);
      setEraOverride(null);
      setDirection(null);
      // ページめくり時にTopにスクロールリセット
      scrollRef.current?.scrollTo({ top: 0 });
    }, 0);
  }, [idx, items.length]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (chatCase) return;
      if (e.key === "ArrowRight") go("right");
      if (e.key === "ArrowLeft") go("left");
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [go, onClose, chatCase]);

  // 防御: idx が変わったら eraOverride を確実に解除する（go 経由以外の遷移が将来追加されても安全）
  useEffect(() => { setEraOverride(null); }, [idx]);

  // body scroll lock
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  const prev = idx > 0 ? items[idx - 1] : null;
  const baseCurr = items[idx];
  // eraGroup タブで切り替えられた場合は override 優先
  const curr = eraOverride && eraOverride.eraGroup === baseCurr?.eraGroup ? eraOverride : baseCurr;
  // 時系列タブ用: 「現在版（canonical=baseCurr）を左、過去（苦闘期）を年昇順で右」に並べる
  const eraGroupCases = useMemo<CaseStudy[]>(() => {
    if (!baseCurr?.eraGroup) return [];
    const all = getEraGroupCases(baseCurr.eraGroup);
    const others = all.filter((e) => e !== baseCurr).sort((a, b) => {
      const ay = typeof a.year === "number" ? a.year : parseInt(String(a.year).match(/\d{3,4}/)?.[0] ?? "0", 10);
      const by = typeof b.year === "number" ? b.year : parseInt(String(b.year).match(/\d{3,4}/)?.[0] ?? "0", 10);
      return ay - by;
    });
    return [baseCurr, ...others];
  }, [baseCurr]);
  const next = idx < items.length - 1 ? items[idx + 1] : null;

  const currSurvivalRaw = pickLocalized(curr?.survivalKey, curr?.survivalKeyEn, locale);
  const currFailRaw = pickLocalized(curr?.failReason, curr?.failReasonEn, locale);
  const currSurvivalKey = currSurvivalRaw && !currSurvivalRaw.includes("上記スコア参照") ? currSurvivalRaw : "";
  const currFailReason = currFailRaw && !currFailRaw.includes("上記スコア参照") ? currFailRaw : "";
  const currSituationLocal = curr ? pickLocalized(curr.situation, curr.situationEn, locale) : "";
  const currCommentLocal = curr ? pickLocalized(curr.otoraComment, curr.otoraCommentEn, locale) : "";
  const chatContext = curr ? (locale === "ja"
    ? `企業名: ${curr.name}\n創業年: ${curr.year}\n総合スコア: ${getCombinedScore(curr)}/100\n12項目: ${curr.total}/60, 3軸: ${(curr.axes.society + curr.axes.customer + curr.axes.self) * 2}/30, ボーナス: +${getBonus(curr, locale).value}\n当時の状況: ${currSituationLocal}\n所感: ${currCommentLocal}\n${currSurvivalKey ? `存続の鍵: ${currSurvivalKey}` : ""}${currFailReason ? `失敗の核心: ${currFailReason}` : ""}\n12項目明細: ${Object.entries(curr.scores).map(([k, v]) => `${SCORE_LABELS_I18N[k]?.ja || k}=${v}`).join(", ")}`
    : `Company: ${curr.name}\nFounded: ${curr.year}\nOverall score: ${getCombinedScore(curr)}/100\n12 criteria: ${curr.total}/60, 3 axes: ${(curr.axes.society + curr.axes.customer + curr.axes.self) * 2}/30, bonus: +${getBonus(curr, locale).value}\nSituation: ${currSituationLocal}\nInsight: ${currCommentLocal}\n${currSurvivalKey ? `Survival key: ${currSurvivalKey}` : ""}${currFailReason ? `Why it failed: ${currFailReason}` : ""}\n12 criteria detail: ${Object.entries(curr.scores).map(([k, v]) => `${SCORE_LABELS_I18N[k]?.en || k}=${v}`).join(", ")}`
  ) : "";

  // 前後2枚ずつ表示（ファイルの束感）
  const stack = [
    idx > 1 ? items[idx - 2] : null,
    prev,
    curr,
    next,
    idx < items.length - 2 ? items[idx + 2] : null,
  ];

  return (
    <div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md" onClick={onClose}>
      {/* 閉じる + ページ番号（控えめ） */}
      <div className="absolute top-3 left-4 z-20">
        <button onClick={onClose} aria-label="閉じる" className="p-2.5 rounded-full bg-card text-foreground shadow-lg hover:text-primary transition-colors">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="absolute top-4 right-4 z-20">
        <span className="text-sm font-bold text-white/80 tabular-nums">{idx + 1} / {items.length}</span>
      </div>

      {/* カードスタック + 矢印 */}
      <div className="absolute inset-0 flex items-center justify-center">
        {/* 左矢印 */}
        {prev && (
          <button
            onClick={(e) => { e.stopPropagation(); go("left"); }}
            className="absolute bottom-3 sm:bottom-auto left-[calc(50%-56px)] sm:left-4 z-20 p-3 rounded-full bg-card text-foreground shadow-lg hover:text-primary transition-all"
          >
            <ChevronLeft className="h-5 w-5 sm:h-6 sm:w-6" />
          </button>
        )}

        {/* カードの束 */}
        <div className="relative w-full max-w-2xl lg:max-w-5xl xl:max-w-6xl max-h-[88dvh] mx-3 sm:mx-16 -mt-14 sm:mt-0" onClick={e => e.stopPropagation()}>
          {/* -2枚目（最背面） */}
          {stack[0] && (
            <div className="hidden md:block absolute inset-x-0 top-0 h-full pointer-events-none" style={{ transform: "translateX(-24px) scale(0.92)", opacity: 0.08, zIndex: 1 }}>
              <div className="h-full rounded-2xl overflow-hidden bg-card border border-border/40">
                <div className="p-3 rounded-t-2xl" style={{ backgroundColor: stack[0].color }}>
                  <p className="text-foreground/70 font-bold text-xs truncate">{stack[0].name}</p>
                </div>
              </div>
            </div>
          )}

          {/* -1枚目 */}
          {stack[1] && (
            <div className="hidden md:block absolute inset-x-0 top-0 h-full pointer-events-none" style={{ transform: "translateX(-12px) scale(0.95)", opacity: 0.2, zIndex: 2 }}>
              <div className="h-full rounded-2xl overflow-hidden bg-card border border-border/40 shadow-lg">
                <div className="p-4 rounded-t-2xl" style={{ backgroundColor: stack[1].color }}>
                  <p className="text-foreground/80 font-bold text-sm truncate">{stack[1].name}</p>
                  <p className="text-muted-foreground/70 text-xs mt-0.5">{getCombinedScore(stack[1])}/100</p>
                </div>
              </div>
            </div>
          )}

          {/* メインカード */}
          <div className="relative" style={{ zIndex: 5 }}>
            <div className="rounded-2xl overflow-hidden bg-card border border-border/60 shadow-2xl max-h-[calc(100dvh-140px)] sm:max-h-[85vh] overflow-y-auto" ref={scrollRef}>
              <div className="text-foreground/90">
                {/* eraGroup を持つ企業は、時系列タブで「現在 ⇄ 苦闘期」を切り替える。
                    左は常に現在版（canonical=baseCurr）、右に過去エントリを年昇順で並べる。 */}
                {eraGroupCases.length > 1 && (
                  <div className="sticky top-0 z-10 flex items-center gap-1.5 border-b border-border/40 bg-card/95 px-4 py-2 backdrop-blur" onClick={(e) => e.stopPropagation()}>
                    {eraGroupCases.map((era, i) => {
                      const active = era === curr;
                      const isCurrent = i === 0; // 先頭は canonical = 現在版
                                            const label = isCurrent
                        ? (locale === "ja" ? "現在" : "Current")
                        : `${era.year}${locale === "ja" ? "年" : ""}`;
                      return (
                        <button
                          key={`era-${era.name}-${era.year}`}
                          type="button"
                          onClick={(e) => { e.stopPropagation(); setEraOverride(era); scrollRef.current?.scrollTo({ top: 0 }); }}
                          className={
                            "rounded-full px-3 py-1 text-xs font-medium transition-colors " +
                            (active
                              ? "bg-foreground text-background"
                              : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground")
                          }
                          aria-pressed={active}
                        >
                          {label}
                        </button>
                      );
                    })}
                  </div>
                )}
                <CardContent c={curr} isLoggedIn={isLoggedIn} onChat={() => setChatCase(curr)} locale={locale} />
              </div>
            </div>
          </div>

          {/* +1枚目 */}
          {stack[3] && (
            <div className="hidden md:block absolute inset-x-0 top-0 h-full pointer-events-none" style={{ transform: "translateX(12px) scale(0.95)", opacity: 0.2, zIndex: 2 }}>
              <div className="h-full rounded-2xl overflow-hidden bg-card border border-border/40 shadow-lg">
                <div className="p-4 rounded-t-2xl" style={{ backgroundColor: stack[3].color }}>
                  <p className="text-foreground/80 font-bold text-sm truncate">{stack[3].name}</p>
                  <p className="text-muted-foreground/70 text-xs mt-0.5">{getCombinedScore(stack[3])}/100</p>
                </div>
              </div>
            </div>
          )}

          {/* +2枚目（最背面） */}
          {stack[4] && (
            <div className="hidden md:block absolute inset-x-0 top-0 h-full pointer-events-none" style={{ transform: "translateX(24px) scale(0.92)", opacity: 0.08, zIndex: 1 }}>
              <div className="h-full rounded-2xl overflow-hidden bg-card border border-border/40">
                <div className="p-3 rounded-t-2xl" style={{ backgroundColor: stack[4].color }}>
                  <p className="text-foreground/70 font-bold text-xs truncate">{stack[4].name}</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 右矢印 */}
        {next && (
          <button
            onClick={(e) => { e.stopPropagation(); go("right"); }}
            className="absolute bottom-3 sm:bottom-auto right-[calc(50%-56px)] sm:right-4 z-20 p-3 rounded-full bg-card text-foreground shadow-lg hover:text-primary transition-all"
          >
            <ChevronRight className="h-5 w-5 sm:h-6 sm:w-6" />
          </button>
        )}
      </div>

      {/* チャットモーダル */}
      {chatCase && (
        <OtoraChat caseName={chatCase.name} context={chatContext} onClose={() => setChatCase(null)} locale={locale} isFail={chatCase.tier === "fail"} />
      )}
    </div>
  );
}

/* ── MLB 風密度テーブル ビュー ── */
// 12軸スコアを左右に広く並べる。数字を主役にして、全社横断比較を容易にする。
// 色: 5=emerald / 4=blue / 3=foreground / 2=amber / 1=red。total は NCG 色帯（survival/excellent）準拠。
function scoreColor(v: number): string {
  if (v >= 5) return "text-(--c-ex)";
  if (v >= 4) return "text-(--c-mean)";
  if (v >= 3) return "text-foreground/80";
  if (v >= 2) return "text-(--c-weak)";
  return "text-(--c-fail)";
}

function CasesTable({
  filtered,
  locale,
  onSelect,
}: {
  filtered: CaseStudy[];
  locale: string;
  onSelect: (idx: number) => void;
}) {
  const ja = locale === "ja";
  // 12軸を略号でヘッダに並べる（MLB カラム風）
  const axes: (keyof CaseScore)[] = [
    "market", "problem", "solution", "team", "traction", "moat",
    "revenue", "financial", "efficiency", "exit", "timing", "insight",
  ];
  const axisShort: Record<keyof CaseScore, string> = {
    market: "MKT", problem: "PRB", solution: "SOL", team: "TEAM",
    traction: "TRC", moat: "MOAT", revenue: "REV", financial: "FIN",
    efficiency: "EFF", exit: "EXIT", timing: "TIME", insight: "INS",
  };

  return (
    <div className="rounded-xl border border-border/60 bg-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-xs tabular-nums">
          <thead className="bg-muted/40 border-b border-border/60 text-muted-foreground">
            <tr>
              <th className="px-3 py-2.5 text-left font-semibold sticky left-0 bg-muted/40 z-10 min-w-[160px]">
                {ja ? "企業" : "Company"}
              </th>
              <th className="px-2 py-2.5 text-right font-semibold" title={ja ? "創業年" : "Founded"}>
                {ja ? "年" : "Yr"}
              </th>
              <th className="px-2 py-2.5 text-right font-semibold" title="NCG">
                NCG
              </th>
              {axes.map((a) => (
                <th
                  key={a}
                  className="px-2 py-2.5 text-center font-semibold"
                  title={ja ? SCORE_LABELS_I18N[a].ja : SCORE_LABELS_I18N[a].en}
                >
                  {axisShort[a]}
                </th>
              ))}
              <th className="px-2 py-2.5 text-right font-semibold" title={ja ? "三方よし平均" : "3-way avg"}>
                3✓
              </th>
              <th className="px-3 py-2.5 text-left font-semibold min-w-[200px]">
                {ja ? "経営の気づき" : "Insight"}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c, idx) => {
              const isFail = c.tier === "fail";
              const total = getCombinedScore(c);
              const totalColor = isFail
                ? "text-(--c-fail)"
                : total >= EXCELLENT_LINE
                ? "text-(--c-ex)"
                : total >= SURVIVAL_LINE
                ? "text-foreground"
                : "text-(--c-weak)";
              const nameColor = isFail
                ? "text-(--c-fail)"
                : total >= EXCELLENT_LINE
                ? "text-(--c-ex)"
                : total >= SURVIVAL_LINE
                ? "text-(--c-mean)"
                : "text-(--c-weak)";
              return (
                <tr
                  key={`${c.name}-${c.year}`}
                  onClick={() => onSelect(idx)}
                  className="border-b border-border/30 last:border-0 hover:bg-muted/30 transition-colors cursor-pointer"
                >
                  <td className="px-3 py-2 sticky left-0 bg-card hover:bg-muted/30 z-10">
                    <div className="flex items-center gap-2">
                      <span
                        className="inline-block w-1 h-6 rounded-full shrink-0"
                        style={{ backgroundColor: c.color }}
                        aria-hidden
                      />
                      {c.flag && <span className="text-sm shrink-0">{c.flag}</span>}
                      <span className={`font-semibold truncate ${nameColor}`}>
                        {locale === "en" && c.nameEn ? c.nameEn : c.name}
                      </span>
                    </div>
                  </td>
                  <td className="px-2 py-2 text-right text-muted-foreground">{c.year}</td>
                  <td className={`px-2 py-2 text-right font-black text-sm ${totalColor}`}>
                    {total}
                  </td>
                  {axes.map((a) => (
                    <td key={a} className={`px-2 py-2 text-center font-semibold ${scoreColor(c.scores[a])}`}>
                      {c.scores[a]}
                    </td>
                  ))}
                  <td className="px-2 py-2 text-right font-semibold text-muted-foreground">
                    {c.axesScore}
                  </td>
                  <td className="px-3 py-2 text-foreground/80 max-w-[320px] truncate">
                    {pickLocalized(c.insight, c.insightEn, locale)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="px-3 py-2 bg-muted/20 border-t border-border/40 text-xs text-muted-foreground flex items-center gap-3 flex-wrap">
        <span className="font-semibold">{ja ? "色凡例" : "Legend"}:</span>
        <span><span className="text-(--c-ex) font-bold">5</span> = {ja ? "卓越" : "excellent"}</span>
        <span><span className="text-(--c-mean) font-bold">4</span> = {ja ? "良" : "good"}</span>
        <span><span className="text-foreground/80 font-bold">3</span> = {ja ? "平均" : "average"}</span>
        <span><span className="text-(--c-weak) font-bold">2</span> = {ja ? "弱" : "weak"}</span>
        <span><span className="text-(--c-fail) font-bold">1</span> = {ja ? "脆弱" : "fragile"}</span>
        <span className="ml-auto">{ja ? "行クリックで詳細" : "Click a row for details"}</span>
      </div>
    </div>
  );
}

/* ── 2D 散布図マップ ビュー ── */
// X軸: axesScore（三方よし平均 0-100）= 社会との調和度
// Y軸: total NCG（0-100）= 総合スコア
// ドット色: tier（カード時と同じ）
// 存続ライン/卓越ラインを水平線で描く → 生存クラスタが視覚的に浮かぶ
function CasesScatterMap({
  filtered,
  locale,
  onSelect,
}: {
  filtered: CaseStudy[];
  locale: string;
  onSelect: (idx: number) => void;
}) {
  const ja = locale === "ja";
  // SVG ビューポート（1 ユニット = 1%、0-100 空間）
  const PAD = { top: 20, right: 20, bottom: 40, left: 40 };
  const W = 720;
  const H = 520;
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const xOf = (v: number) => PAD.left + (v / 100) * innerW;
  const yOf = (v: number) => PAD.top + (1 - v / 100) * innerH;

  // indexOf で元配列のインデックスを取る（モーダルと連動するため）
  const indexMap = new Map<CaseStudy, number>();
  filtered.forEach((c, i) => indexMap.set(c, i));

  const survivalY = yOf(SURVIVAL_LINE);
  const excellentY = yOf(EXCELLENT_LINE);

  return (
    <div className="rounded-xl border border-border/60 bg-card p-3 sm:p-4">
      <div className="mb-3 flex items-center justify-between gap-2 flex-wrap">
        <div>
          <p className="text-sm font-semibold">
            {ja ? "NCG マップ — 全社の位置関係" : "NCG Map — positions at a glance"}
          </p>
          <p className="text-xs text-muted-foreground">
            {ja
              ? "横軸: 三方よし平均（社会・顧客・自己の調和度）／ 縦軸: NCG 総合スコア"
              : "X: 3-way average (society/customer/self balance) ／ Y: Total NCG score"}
          </p>
        </div>
        <p className="text-xs text-muted-foreground">
          {ja ? "ドットクリックで詳細" : "Click a dot for details"}
        </p>
      </div>

      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-auto max-w-none"
          style={{ minWidth: 640 }}
          role="img"
          aria-label={ja ? "全社 NCG 散布図" : "Companies NCG scatter"}
        >
          {/* 背景ゾーン: 卓越ゾーン（EXCELLENT_LINE より上） */}
          <rect
            x={PAD.left}
            y={PAD.top}
            width={innerW}
            height={excellentY - PAD.top}
            fill="rgba(46,110,78,0.05)"
          />
          {/* 危険ゾーン（SURVIVAL_LINE より下） */}
          <rect
            x={PAD.left}
            y={survivalY}
            width={innerW}
            height={PAD.top + innerH - survivalY}
            fill="rgba(166,58,36,0.05)"
          />

          {/* グリッド線 */}
          {[0, 25, 50, 75, 100].map((v) => (
            <g key={`gx-${v}`}>
              <line
                x1={xOf(v)}
                y1={PAD.top}
                x2={xOf(v)}
                y2={PAD.top + innerH}
                stroke="currentColor"
                strokeOpacity={v === 0 || v === 100 ? 0.2 : 0.08}
                strokeDasharray={v === 0 || v === 100 ? "none" : "2 3"}
              />
              <text
                x={xOf(v)}
                y={H - PAD.bottom + 16}
                textAnchor="middle"
                fontSize={10}
                className="fill-muted-foreground"
              >
                {v}
              </text>
            </g>
          ))}
          {[0, 25, 50, 75, 100].map((v) => (
            <g key={`gy-${v}`}>
              <line
                x1={PAD.left}
                y1={yOf(v)}
                x2={PAD.left + innerW}
                y2={yOf(v)}
                stroke="currentColor"
                strokeOpacity={v === 0 || v === 100 ? 0.2 : 0.08}
                strokeDasharray={v === 0 || v === 100 ? "none" : "2 3"}
              />
              <text
                x={PAD.left - 6}
                y={yOf(v) + 3}
                textAnchor="end"
                fontSize={10}
                className="fill-muted-foreground"
              >
                {v}
              </text>
            </g>
          ))}

          {/* ライン: 存続/卓越 */}
          <line
            x1={PAD.left}
            y1={survivalY}
            x2={PAD.left + innerW}
            y2={survivalY}
            stroke="#a63a24"
            strokeOpacity={0.45}
            strokeDasharray="4 4"
          />
          <text x={PAD.left + 6} y={survivalY - 4} fontSize={10} fill="#a63a24" opacity={0.8}>
            {ja ? `存続ライン ${SURVIVAL_LINE}` : `Survival ${SURVIVAL_LINE}`}
          </text>
          <line
            x1={PAD.left}
            y1={excellentY}
            x2={PAD.left + innerW}
            y2={excellentY}
            stroke="#2e6e4e"
            strokeOpacity={0.45}
            strokeDasharray="4 4"
          />
          <text x={PAD.left + 6} y={excellentY - 4} fontSize={10} fill="#2e6e4e" opacity={0.8}>
            {ja ? `卓越ライン ${EXCELLENT_LINE}` : `Excellent ${EXCELLENT_LINE}`}
          </text>

          {/* 軸ラベル */}
          <text
            x={PAD.left + innerW / 2}
            y={H - 4}
            textAnchor="middle"
            fontSize={11}
            className="fill-muted-foreground font-semibold"
          >
            {ja ? "三方よし平均（社会・顧客・自己）→" : "3-way average (society · customer · self) →"}
          </text>
          <text
            x={-(PAD.top + innerH / 2)}
            y={12}
            textAnchor="middle"
            fontSize={11}
            transform="rotate(-90)"
            className="fill-muted-foreground font-semibold"
          >
            {ja ? "← NCG 総合スコア" : "← Total NCG"}
          </text>

          {/* ドット */}
          {filtered.map((c) => {
            const x = xOf(c.axesScore);
            const y = yOf(getCombinedScore(c));
            const idx = indexMap.get(c) ?? 0;
            const isFail = c.tier === "fail";
            return (
              <g key={`${c.name}-${c.year}`}>
                <title>
                  {`${c.name} (${c.year})\nNCG: ${getCombinedScore(c)} / 100\n三方よし: ${c.axesScore}\n${pickLocalized(c.insight, c.insightEn, locale)}`}
                </title>
                <circle
                  cx={x}
                  cy={y}
                  r={isFail ? 4 : 5.5}
                  fill={c.color}
                  fillOpacity={0.85}
                  stroke="white"
                  strokeWidth={0.8}
                  onClick={() => onSelect(idx)}
                  className="cursor-pointer hover:opacity-100 transition-opacity"
                  style={{ opacity: 0.9 }}
                />
              </g>
            );
          })}
        </svg>
      </div>

      <div className="mt-3 text-xs text-muted-foreground flex items-center gap-3 flex-wrap">
        <span>
          <span className="inline-block w-2 h-2 rounded-full bg-(--c-ex) mr-1" />
          {ja ? "卓越ゾーン" : "Excellent zone"}
        </span>
        <span>
          <span className="inline-block w-2 h-2 rounded-full bg-(--c-fail) mr-1" />
          {ja ? "危険ゾーン" : "Danger zone"}
        </span>
        <span className="ml-auto">
          {ja ? `表示中: ${filtered.length}社 / ホバーで詳細` : `Shown: ${filtered.length} / hover for details`}
        </span>
      </div>
    </div>
  );
}


/* ── メインページ ── */
export default function CasesPage() {
  const { data: session } = useSession();
  const { locale } = useLocale();
  const isLoggedIn = !!session?.user;
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const [viewMode, setViewMode] = useState<"card" | "table" | "map">("card");
  const gridTopRef = useRef<HTMLDivElement>(null);

  // URL `?view=table` を初期値に反映（シェア時の意図を保つ）
  useEffect(() => {
    if (typeof window === "undefined") return;
    const v = new URLSearchParams(window.location.search).get("view");
    if (v === "card") setViewMode(v);
  }, []);

  // viewMode 変更時に URL も更新（履歴は push せず replace）
  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    if (viewMode === "table") url.searchParams.set("view", "table");
    else if (viewMode === "map") url.searchParams.set("view", "map");
    else url.searchParams.delete("view");
    window.history.replaceState({}, "", url.toString());
  }, [viewMode]);

  const tiers = ["all", "god", "earth", "startup", "fail", "japan", "social", "bronze", "silver", "gold"];
  const tierLabels: Record<string, string> = locale === "ja"
    ? { all: "全て", god: "W10", earth: "アース30", craft: "クラフト", startup: "スタートアップ", fail: "失敗", japan: "日本企業", social: "ソーシャル", bronze: "100年+", silver: "300年+", gold: "500年+" }
    : { all: "All", god: "W10", earth: "Earth 30", craft: "Craft", startup: "Startup", fail: "Failed", japan: "Japan", social: "Social", bronze: "100yr+", silver: "300yr+", gold: "500yr+" };

  // 同一企業の eraGroup（例: SpaceX 2002/2024）は tier ランクが高い canonical 1社だけを
  // 一覧に出す。モーダル内のタブで時系列の進化を見せる。
  // CASE_STUDIES は不変なので useMemo で正準セットを一度だけ計算する（200+件の Map 走査）。
  const canonicalCases = useMemo(() => getCanonicalCases(), []);
  const filtered = useMemo(
    () => canonicalCases.filter((c) => matchesFilter(filter, c)),
    [canonicalCases, filter]
  );

  // タグ切替時、カードグリッドの先頭までスクロール（スティッキーヘッダー分のオフセットを考慮）
  const selectTier = useCallback((t: string) => {
    setFilter(t);
    setSelectedIdx(null);
    requestAnimationFrame(() => {
      if (gridTopRef.current) {
        const rect = gridTopRef.current.getBoundingClientRect();
        const top = window.scrollY + rect.top - 140;
        window.scrollTo({ top, behavior: "smooth" });
      }
    });
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8">
      <div className="space-y-6">
        <header className="space-y-4">
          <p className="text-xs font-bold tracking-[0.3em] text-primary">ARCHE — COMPANY CASES</p>
          <h1 className="[font-family:var(--font-serif)] text-[26px] sm:text-[34px] font-bold leading-[1.4] text-foreground">
            企業の構造分析<span className="ml-3 text-base sm:text-lg font-bold text-muted-foreground">アルケー</span>
          </h1>
          <p className="text-[15px] leading-[1.9] text-foreground max-w-3xl">
            世界を変えた企業{canonicalCases.length}社を、同じ物差しで並べました。
          </p>
          {/* 採点の説明は折りたたむ（冒頭の文字が多すぎた・2026-10-18） */}
          <details className="group max-w-3xl text-[14px] leading-[1.9] text-muted-foreground">
            <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 text-[13px] font-bold text-primary [&::-webkit-details-marker]:hidden">
              採点のしかた
              <span className="transition-transform group-open:rotate-180" aria-hidden="true">▾</span>
            </summary>
            <p className="mt-2">
              市場・課題・チームなど12項目（各5点）と、世間・相手・自己の三軸（各10点）で採点し、100点満点で表しています。長く続いた会社と消えた会社の差が、どこに出るかを見るための一覧です。
            </p>
          </details>
          <ul className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-foreground">
            <li className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm bg-(--c-ex)" />卓越 {EXCELLENT_LINE}点以上</li>
            <li className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm bg-(--c-mean)" />中庸 {SURVIVAL_LINE}点以上</li>
            <li className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm bg-(--c-weak)" />脆弱 {SURVIVAL_LINE}点未満</li>
            <li className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm bg-(--c-fail)" />失敗した企業</li>
          </ul>
        </header>

        {/* フィルター（1行横スクロール・コンパクト） */}
        <div className="sm:sticky sm:top-16 z-10 bg-background/95 backdrop-blur-sm -mx-4 sm:-mx-6 px-4 sm:px-6 py-3 border-y border-border">
          <div className="flex items-start gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex flex-nowrap sm:flex-wrap items-center gap-2 overflow-x-auto sm:overflow-visible [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">

                {tiers.map((t) => (
                  <button
                    key={t}
                    onClick={() => selectTier(t)}
                    className={`rounded-full px-3.5 py-1.5 text-[13px] font-bold transition-colors shrink-0 border ${
                      filter === t ? "bg-foreground text-background border-foreground" : "bg-card text-foreground border-border hover:border-primary hover:text-primary"
                    }`}
                  >
                    {tierLabels[t]}
                  </button>
                ))}
              </div>
            </div>
            <span className="text-sm font-bold text-muted-foreground shrink-0 pt-1.5 tabular-nums">{filtered.length}{locale === "ja" ? "社" : ""}</span>
          </div>
        </div>

        <div ref={gridTopRef} aria-hidden="true" />


        {/* カードグリッド or テーブル or マップ */}
        {viewMode === "map" ? (
          <CasesScatterMap filtered={filtered} locale={locale} onSelect={setSelectedIdx} />
        ) : viewMode === "table" ? (
          <CasesTable filtered={filtered} locale={locale} onSelect={setSelectedIdx} />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {filtered.map((c, idx) => {
              const tierInfo = TIER_CONFIG_I18N[c.tier];
              const isFail = c.tier === "fail";
              return (
                <button
                  key={`${c.name}-${c.year}`}
                  onClick={() => setSelectedIdx(idx)}
                  className={`group text-left rounded-xl overflow-hidden border hover:shadow-md transition-all bg-card ${TIER_BORDER[c.tier]} ${TIER_ACCENT[c.tier]}`}
                >
                  <div className="flex gap-3 p-3">
                    {/* ジャケット */}
                    <div
                      className="w-12 h-12 shrink-0 rounded-lg flex items-center justify-center relative"
                      style={{ backgroundColor: c.color }}
                    >
                      <span className="text-lg font-black text-white drop-shadow-md">{c.initial}</span>
                    </div>
                    {/* 情報 */}
                    <div className="flex-1 min-w-0">
                      <p className="text-base sm:text-sm font-semibold truncate">{locale === "en" && c.nameEn ? c.nameEn : c.name}</p>
                      <p className="text-sm sm:text-xs text-foreground/75 mt-0.5 leading-snug line-clamp-1">{pickLocalized(c.insight, c.insightEn, locale)}</p>
                      {(pickLocalized(c.virtue, c.virtueEn, locale)) && <span className="inline-block mt-1 text-xs sm:text-[11px] tracking-[-0.02em] text-primary bg-primary/10 px-1 py-0.5 rounded">{pickLocalized(c.virtue, c.virtueEn, locale)}</span>}
                    </div>
                    {/* スコア + 三方よしチャート（頂点ラベル付き・点数重ね、100点満点） */}
                    <div className="shrink-0 relative w-20 h-20 flex items-center justify-center">
                      <div className="absolute inset-0 flex items-center justify-center opacity-50">
                        <TriangleChart
                          axes={c.axes}
                          size={80}
                          showLabels
                          locale={locale}
                          color={isFail ? "#a63a24" : getCombinedScore(c) >= EXCELLENT_LINE ? "#2e6e4e" : "#30557e"}
                        />
                      </div>
                      <span className={`text-xl font-black relative z-10 ${
                        isFail ? "text-(--c-fail)" : getCombinedScore(c) >= EXCELLENT_LINE ? "text-(--c-ex)" : "text-foreground"
                      }`}>{getCombinedScore(c)}</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {/* 分析手法（ピッチ診断と同じ採点基盤） */}
        <MethodologySection locale={locale} />

        {/* 法則セクション */}
        <div className="rounded-xl border border-border/60 bg-muted/30 p-5 space-y-3 mt-4">
          <p className="k-h text-foreground">{locale === "ja" ? "5つの生存法則" : "5 Laws of Survival"}</p>
          {locale === "ja" ? (
            <div className="grid gap-2 text-sm leading-[1.8]">
              <p><span className="font-semibold">1.</span> 存続ラインは47点（100点満点）。ただしTiming 5 + Insight 5なら47点以下でも生存可能</p>
              <p><span className="font-semibold">2.</span> Moatは「育てるもの」。スタートアップ平均2.4→レジェンド平均4.6</p>
              <p><span className="font-semibold">3.</span> 失敗企業に共通するのはInsight 1点。$1.75Bでも$700Mでも死ぬ</p>
              <p><span className="font-semibold">4.</span> レジェンドは「成長しない勇気」で生き残る</p>
              <p><span className="font-semibold">5.</span> 「何で稼いでいるか」と「何で生き残っているか」は違う</p>
            </div>
          ) : (
            <div className="grid gap-2 text-sm leading-[1.8]">
              <p><span className="font-semibold">1.</span> Survival Line = 47 (out of 100). But Timing 5 + Insight 5 can override.</p>
              <p><span className="font-semibold">2.</span> Moat is built, not born. Startup avg 2.4 → Legend avg 4.6.</p>
              <p><span className="font-semibold">3.</span> Failed companies share Insight = 1. $1.75B or $700M — still dead.</p>
              <p><span className="font-semibold">4.</span> Legends survive by the courage NOT to grow.</p>
              <p><span className="font-semibold">5.</span> What makes money ≠ What keeps you alive.</p>
            </div>
          )}
        </div>

        <JudgmentFoundation locale={locale} />

        <div className="mt-10"><NgraphCta /></div>
      </div>

      {/* スライダーモーダル */}
      {selectedIdx !== null && (
        <SliderModal
          items={filtered}
          initialIdx={selectedIdx}
          isLoggedIn={isLoggedIn}
          onClose={() => setSelectedIdx(null)}
          locale={locale}
        />
      )}
    </div>
  );
}
