"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

type Locale = "ja" | "en";

interface Pillar {
  greek: string;
  letter: string;
  term_ja: string;
  term_en: string;
  short_ja: string;
  short_en: string;
  desc_ja: string;
  desc_en: string;
}

const PILLARS: Pillar[] = [
  {
    greek: "Eudaimonia",
    letter: "Ε",
    term_ja: "エウダイモニア",
    term_en: "Eudaimonia",
    short_ja: "幸福",
    short_en: "Flourishing",
    desc_ja: "事業の目的は利益ではなく、関わる全員の「よく生きる」こと",
    desc_en: "The purpose of business is not profit, but helping everyone involved live well.",
  },
  {
    greek: "Arete",
    letter: "Α",
    term_ja: "アレテー",
    term_en: "Arete",
    short_ja: "卓越性",
    short_en: "Excellence",
    desc_ja: "自分の役割を最高の形で果たすこと",
    desc_en: "Performing one's role at the highest possible level.",
  },
  {
    greek: "Mesotes",
    letter: "Μ",
    term_ja: "メソテース",
    term_en: "Mesotes",
    short_ja: "中庸",
    short_en: "The Golden Mean",
    desc_ja: "極端を避け、状況に応じた最善を重ねる",
    desc_en: "Avoiding extremes, accumulating context-appropriate best choices.",
  },
  {
    greek: "Phronesis",
    letter: "Π",
    term_ja: "プロネーシス",
    term_en: "Phronesis",
    short_ja: "実践知",
    short_en: "Practical Wisdom",
    desc_ja: "この状況・この人にとっての最善を見極める知恵",
    desc_en: "The wisdom to discern what is best for this situation and this person.",
  },
  {
    greek: "Hexis",
    letter: "Η",
    term_ja: "ヘクシス",
    term_en: "Hexis",
    short_ja: "習慣的性向",
    short_en: "Habitual Disposition",
    desc_ja: "日々の判断の積み重ねが事業の性格を作る",
    desc_en: "Daily decisions accumulate into the character of a business.",
  },
  {
    greek: "Philia",
    letter: "Φ",
    term_ja: "フィリア",
    term_en: "Philia",
    short_ja: "友愛",
    short_en: "Friendship",
    desc_ja: "取引先・従業員・顧客との信頼関係こそ最大の資産",
    desc_en: "Trust with partners, employees, and customers is the greatest asset.",
  },
];

interface JudgmentFoundationProps {
  locale?: Locale;
  defaultOpen?: boolean;
}

export function JudgmentFoundation({ locale = "ja", defaultOpen = false }: JudgmentFoundationProps) {
  const [open, setOpen] = useState(defaultOpen);
  const title = locale === "en" ? "Foundation — Nicomachean Ethics" : "判断基盤 — ニコマコス倫理学";
  const hint = locale === "en" ? "The six pillars guiding every score and dialogue." : "すべての採点と対話の土台となる六つの柱";

  return (
    <section className="rounded-2xl border border-border/60 bg-muted/20 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-3 px-4 sm:px-5 py-3 text-left hover:bg-muted/40 transition"
        aria-expanded={open}
      >
        <div className="min-w-0">
          <p className="text-xs font-bold text-primary uppercase tracking-widest">{title}</p>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{hint}</p>
        </div>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="border-t border-border/60 px-4 sm:px-5 py-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {PILLARS.map((p) => (
            <div
              key={p.greek}
              className="rounded-xl border border-border/40 bg-background/60 p-3 flex gap-3"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary text-xl font-serif">
                {p.letter}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-1.5 flex-wrap">
                  <span className="text-sm font-bold">
                    {locale === "en" ? p.term_en : p.term_ja}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {locale === "en" ? p.short_en : p.short_ja}
                  </span>
                </div>
                <p className="text-xs text-foreground/70 mt-1 leading-relaxed">
                  {locale === "en" ? p.desc_en : p.desc_ja}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
