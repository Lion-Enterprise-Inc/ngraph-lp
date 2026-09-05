// 日本語の折返しを語句単位にする（2026-09-05）。
// Chrome は word-break:auto-phrase で語句単位に折るが、Safari(iPhone)/Firefox は未対応で
// 「業務が変/わるたびに」のように語の途中で折れる。BudouX（Chromeの auto-phrase と同じモデル）で
// 語句の切れ目にゼロ幅スペースを入れ、.bdx{word-break:keep-all} で切れ目以外では折らせない。
// 読み込みは worker.js が全HTMLの <head> 末尾に差し込む（記事97本にタグを書かずに済ませるため）。
(function () {
  var lang = document.documentElement.lang || 'ja';
  if (!/^ja/i.test(lang)) return;
  var hasAutoPhrase = !!(window.CSS && CSS.supports && CSS.supports('word-break', 'auto-phrase'));
  var narrow = window.matchMedia && matchMedia('(max-width:768px)').matches;
  if (hasAutoPhrase && !narrow) return; // PCのChromeはこれまで通り auto-phrase に任せる

  function run() {
    if (!window.budoux) return;
    var proc = new budoux.HTMLProcessor(new budoux.Parser(budoux.model), { className: 'bdx' });
    var sel = 'p,li,dd,dt,h1,h2,h3,h4,td,th,summary,figcaption,blockquote,.fg';
    document.querySelectorAll(sel).forEach(function (el) {
      if (el.closest('pre,code,script,style,.no-bdx')) return;
      try { proc.applyToElement(el); } catch (e) { /* 1要素の失敗で全体を止めない */ }
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
