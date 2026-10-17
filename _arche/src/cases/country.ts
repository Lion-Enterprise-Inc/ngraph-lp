// 国旗の絵文字（Windows では「US」のような文字で出る）を、日本語の国名にする
const NAMES: Record<string, string> = {
  US: "米国", JP: "日本", CN: "中国", IT: "イタリア", FR: "フランス", GB: "英国", DE: "ドイツ",
  SE: "スウェーデン", KR: "韓国", IN: "インド", BD: "バングラデシュ", AU: "オーストラリア",
  NL: "オランダ", CH: "スイス", DK: "デンマーク", CA: "カナダ", IL: "イスラエル", BR: "ブラジル",
  TW: "台湾", SG: "シンガポール", KE: "ケニア", FI: "フィンランド", ES: "スペイン",
  AT: "オーストリア", BE: "ベルギー", NO: "ノルウェー", GH: "ガーナ", BS: "バハマ",
};

export function countryName(flag?: string): string {
  if (!flag) return "";
  const code = [...flag]
    .map((ch) => ch.codePointAt(0) ?? 0)
    .filter((cp) => cp >= 0x1f1e6 && cp <= 0x1f1ff)
    .map((cp) => String.fromCharCode(cp - 0x1f1e6 + 65))
    .join("");
  return NAMES[code] ?? code;
}
