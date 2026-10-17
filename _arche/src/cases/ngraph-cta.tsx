// 一覧と各社ページの最後に置く、ngraph.jp の AI導入支援への案内（2026-10-18 本人「5を入れて」）。
// 文言は /fde/ に書いてあること（エンジニアが現場に入り、業務・判断・使っているデータを見てから組み込む）だけで作る。
// FDE の現場でアルケーの採点をしている、とは書かない（事実ではない）。
export function NgraphCta() {
  return (
    <section className="rounded-xl border border-border bg-card p-5 sm:p-6">
      <p className="text-xs font-bold tracking-[0.3em] text-primary">NGRAPH — AI導入支援</p>
      <h2 className="mt-2 [font-family:var(--font-serif)] text-lg sm:text-xl font-bold leading-[1.5] text-foreground">
        事業を構造でつかむところから、AI導入に入ります
      </h2>
      <p className="mt-2 text-[15px] leading-[1.9] text-foreground">
        NGraphは、エンジニアが御社の現場に入り、業務・判断・使っているデータを見てからAIを組み込みます。使い方を教えて終わりではなく、現場で使われる状態をつくって残します。
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <a href="/fde/" className="inline-flex items-center rounded-full bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground hover:opacity-90 transition-opacity">
          AI導入支援を見る →
        </a>
        <a href="/entry" className="inline-flex items-center rounded-full border border-border bg-background px-5 py-2.5 text-sm font-bold text-foreground hover:border-primary hover:text-primary transition-colors">
          無料で相談する
        </a>
      </div>
    </section>
  );
}
