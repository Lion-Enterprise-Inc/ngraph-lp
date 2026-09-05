// 日本語の折返しを語句単位にする（2026-09-05）。
// Chrome は word-break:auto-phrase で語句単位に折るが、Safari(iPhone)/Firefox は未対応で
// 「業務が変/わるたびに」のように語の途中で折れる。BudouX（Chromeの auto-phrase と同じモデル）で
// 語句の切れ目にゼロ幅スペースを入れ、word-break:keep-all（inline style）で切れ目以外では折らせない。
// 読み込みは worker.js が全HTMLの <head> 末尾に差し込む（記事97本にタグを書かずに済ませるため）。
(function () {
  var lang = document.documentElement.lang || 'ja';
  if (!/^ja/i.test(lang)) return;
  var hasAutoPhrase = !!(window.CSS && CSS.supports && CSS.supports('word-break', 'auto-phrase'));
  var narrow = window.matchMedia && matchMedia('(max-width:768px)').matches;
  if (hasAutoPhrase && !narrow) return; // PCのChromeはこれまで通り auto-phrase に任せる

  function run() {
    if (!window.budoux) return;
    // className を渡さず、BudouX 標準の inline style（word-break:keep-all; overflow-wrap:anywhere）で効かせる。
    // 記事ページは sp.css を読まないので、CSSに頼らず要素自身に持たせる（inline style は既存のどの規則にも勝つ）
    var proc = new budoux.HTMLProcessor(new budoux.Parser(budoux.model));
    var sel = 'p,li,dd,dt,h1,h2,h3,h4,td,th,summary,figcaption,blockquote,.fg';
    document.querySelectorAll(sel).forEach(function (el) {
      if (el.closest('pre,code,script,style,.no-bdx,[data-bdx]')) return; // 処理済みの中は二重に入れない
      try { proc.applyToElement(el); el.setAttribute('data-bdx', ''); } catch (e) { /* 1要素の失敗で全体を止めない */ }
    });
    document.documentElement.classList.add('bdx-on');
  }
  function start() {
    var s = document.createElement('script');
    s.src = '/js/budoux-ja.min.js?v=1';
    s.onload = run;
    document.head.appendChild(s);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
