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
    var skip = 'pre,code,script,style,.no-bdx,[data-bdx]';
    // 第2パスだけ、フォーム・ボタン・図の中も除く（ボタンの文字は業種名などをJSが読み取ることがある）
    var skip2 = skip + ',svg,form,button,textarea,select';
    function apply(el, sk) {
      if (el.closest(sk || skip)) return; // 処理済みの中は二重に入れない
      try { proc.applyToElement(el); el.setAttribute('data-bdx', ''); } catch (e) { /* 1要素の失敗で全体を止めない */ }
    }
    document.querySelectorAll(sel).forEach(function (el) { apply(el); });
    // 第2パス（2026-10-31）：p・li などに入っていない div / span 直下の文字も語句で折る。
    // 比較表のセルや図の札が div なので、iPhone では「AI会／社の」「保管され／るかを」と語の途中で折れていた。
    // 記事（/blog/<記事>・/cases/<事例>）は計算ツールなど個別のJSを持つものがあり全件の実機確認ができないため、第2パスの対象外にする
    var isArticle = /^\/(blog|cases)\/[^/]+/.test(location.pathname);
    if (!isArticle) document.querySelectorAll('div,span,small,b,strong,em').forEach(function (el) {
      var own = false;
      for (var i = 0; i < el.childNodes.length; i++) { var n = el.childNodes[i]; if (n.nodeType === 3 && /\S/.test(n.nodeValue)) { own = true; break; } }
      if (own) apply(el, skip2);
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
