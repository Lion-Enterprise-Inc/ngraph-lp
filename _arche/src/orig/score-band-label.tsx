"use client";

import { useLocale } from "@/lib/i18n/context";

export type ScoreBandKind = "deviation" | "excellence" | "mean" | "fragile";

const LABELS: Record<ScoreBandKind, { ja: string; en: string }> = {
  deviation: { ja: "赤（逸脱）", en: "Red (Deviation)" },
  excellence: { ja: "緑（卓越・アレテー）", en: "Green (Excellence — Arete)" },
  mean: { ja: "青（中庸・メソテース）", en: "Blue (Golden Mean — Mesotes)" },
  fragile: { ja: "黄（脆弱）", en: "Yellow (Fragile)" },
};

export function ScoreBandLabel({ kind }: { kind: ScoreBandKind }) {
  const { locale } = useLocale();
  return <>{LABELS[kind][locale as "ja" | "en"]}</>;
}
