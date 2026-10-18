// 取引先チェックの結果を「結論の3行＋4つの欄＋自分で確かめるリンク」に組み立てる。
// 原則: 決定的なルールだけで書く（LLMに書かせない）。会社の良し悪しは書かず、
// 裏が取れたこと・取れなかったこと・契約前にすることだけを書く。

const AREAS = Object.freeze([
  { key: 'identity', title: '実在と同一性', note: '登記の会社と、サイトの会社が同じか' },
  { key: 'contact', title: '連絡先', note: '住所・電話・メールで連絡がつくか' },
  { key: 'age', title: '会社の年齢と規模', note: 'いつからあるか、どのくらいの規模を名乗っているか' },
  { key: 'public', title: '公的な活動', note: '届出・認定、補助金、公共調達、表彰の記録' },
]);

const AREA_BY_LABEL = [
  [/^法人の自動特定|^法人候補|^サイト所在地と登記|^商号（登記）|^本店所在地|^代表者|^インボイス登録（|^公表されている|^インボイス公表情報/, 'identity'],
  [/^メール受信|^送信ドメイン|^電話番号|^SNS/, 'contact'],
  [/^ドメイン登録日|^設立|^資本金|^従業員数|^インボイス登録年月日|^ブログ/, 'age'],
  [/^届出・認定|^補助金交付|^公共調達|^表彰/, 'public'],
];

// 画面に出す状態は5つに揃える。
export const STATE = Object.freeze({
  '確認済': '確認できた',
  '食い違い': '食い違い',
  'サイトの記載': 'サイトの記載（自己申告）',
  '情報なし': '届出なし',
  '未確認': '調べきれていない',
  '対象外': '自動では調べていない',
  '取得失敗': '取得できず',
});

export function areaOf(label) {
  const hit = AREA_BY_LABEL.find(([pattern]) => pattern.test(String(label || '')));
  return hit ? hit[1] : null;
}

const value = (facts, label) => facts.find(fact => fact.label.startsWith(label));
const confirmed = (facts, label) => {
  const fact = value(facts, label);
  return fact && fact.status === '確認済' ? fact : null;
};

function monthsBetween(isoDate, now) {
  const date = new Date(String(isoDate || '').slice(0, 10));
  if (Number.isNaN(date.getTime())) return null;
  return (now.getFullYear() - date.getFullYear()) * 12 + (now.getMonth() - date.getMonth());
}

function ageText(months) {
  if (months < 1) return '1か月以内';
  if (months < 24) return `${months}か月前`;
  return `${Math.floor(months / 12)}年前`;
}

// 公的な活動4件がすべて0件なら1行にまとめる（0件が4行並ぶと何も分からない画面に見える）。
function collapsePublic(rows) {
  const counts = rows.filter(row => row.status === '確認済' && /^\d+件$/.test(String(row.value)));
  if (counts.length === 4 && counts.every(row => row.value === '0件')) {
    return [{ label: '届出・認定／補助金／公共調達／表彰', value: 'gBizINFO にはどれも記録なし（0件）。小さな会社では普通のことです', status: '確認済', source: 'gBizINFO' }];
  }
  return rows;
}

export function sectionsOf(facts) {
  return AREAS.map(area => {
    let rows = facts.filter(fact => areaOf(fact.label) === area.key);
    if (area.key === 'public') rows = collapsePublic(rows);
    rows = rows.map(row => ({ ...row, state: STATE[row.status] || row.status }));
    return { ...area, rows };
  }).filter(section => section.rows.length);
}

// 403・429 などはサイトはあるが機械の取得を断った状態。「サイトが無い」と混同しない。
const refused = context => /^http_(?:401|403|429|503)$/.test(String(context.siteFailReason || ''));

export function buildSummary(facts, context = {}) {
  const now = context.now || new Date();
  const corp = context.corporation || null;
  const got = [];
  const missing = [];
  const actions = [];

  if (corp && context.resolved) {
    got.push(`登記の会社を特定：${corp.name}（法人番号 ${corp.corporate_number}）`);
    const match = value(facts, 'サイト所在地と登記');
    if (match?.status === '確認済') got.push('サイトの住所と登記の住所は番地まで一致');
    if (match?.status === '食い違い') missing.push('サイトの住所と登記の住所が一致しない');
  } else if (context.mode === 'site' && context.siteFailed) {
    missing.push(refused(context)
      ? `サイトが自動の取得を断った（${context.siteFailReason}）ため、登記の会社と照らし合わせていない`
      : 'サイトを開けなかったため、登記の会社と照らし合わせていない');
  } else if (context.mode === 'site') {
    missing.push(context.candidateCount === 1
      ? `サイトの社名と同じ名前の法人は1社あるが、サイトから住所・法人番号が取れず、同じ会社だとは確かめられていない`
      : context.candidateCount
        ? `サイトの会社を登記の1社に絞れなかった（同じ名前の候補 ${context.candidateCount} 社）`
        : 'サイトから登記の会社を特定できなかった');
  }

  const invoice = value(facts, 'インボイス登録（');
  const invoiceDate = confirmed(facts, 'インボイス登録年月日');
  if (invoice?.status === '確認済') {
    if (/登録取消|登録失効/.test(invoice.value)) missing.push('インボイス登録が取消・失効になっている');
    else if (/^登録あり/.test(invoice.value)) got.push(`インボイス登録あり${invoiceDate ? `（${invoiceDate.value}）` : ''}`);
    else if (/^登録なし/.test(invoice.value)) missing.push('インボイス登録なし（免税事業者なら普通）');
  }
  const invoiceMatch = value(facts, 'インボイス公表情報');
  if (invoiceMatch?.status === '食い違い') missing.push('インボイスの公表名・住所が登記と一致しない');

  const phone = confirmed(facts, '電話番号（サイト記載');
  if (phone) got.push(`電話番号の記載あり（${String(phone.value).split(' / ')[0]}）`);
  else if (context.mode === 'site' && !context.siteFailed) missing.push('サイトの会社情報ページに電話番号が見当たらない');

  const mx = confirmed(facts, 'メール受信');
  if (mx && /^なし/.test(mx.value)) missing.push('このドメインはメールを受け取れない設定');

  const notFiled = ['設立', '資本金', '従業員数（届出'].filter(label => value(facts, label)?.status === '情報なし')
    .map(label => label.replace('（届出', ''));
  if (notFiled.length) missing.push(`${notFiled.join('・')}は公的DBに届出なし`);

  // 会社の若さ：設立日・ドメイン取得日・インボイス登録日のうち、取れたものだけで言う。
  const dates = [
    ['設立', confirmed(facts, '設立')?.value],
    ['ドメイン取得', confirmed(facts, 'ドメイン登録日')?.value],
  ].filter(([, date]) => date);
  const young = dates.map(([label, date]) => [label, monthsBetween(date, now)])
    .filter(([, months]) => months !== null && months < 24);
  for (const [label, months] of young) missing.push(`${label}は${ageText(months)}`);

  // 契約前にすること（最大3つ。上ほど優先）
  if (context.mode === 'site' && context.siteFailed) {
    actions.push(refused(context)
      ? 'ブラウザでサイトの会社概要を開き、載っている法人番号か社名でもう一度調べる'
      : 'URLが正しいかを相手に確かめる。サイトが無いなら、法人番号でもう一度調べる');
  } else if (context.mode === 'site' && !context.resolved) {
    actions.push(context.candidateCount === 1
      ? '下の候補が相手の会社か、相手に法人番号を出してもらって確かめる'
      : '相手に法人番号（または登記簿謄本）を出してもらい、その番号でもう一度調べる');
  }
  if (missing.some(item => /住所が一致しない|一致しない/.test(item))) {
    actions.push('サイトや請求書の住所と登記の住所が違う理由を聞く');
  }
  if (young.length || notFiled.includes('設立') || (mx && /^なし/.test(mx.value))) {
    actions.push('初回は前払いを避け、納品と引き換えの支払いにする');
  }
  actions.push('登記簿謄本（履歴事項全部証明書）で、代表者と本店移転の履歴を見る');
  actions.push('いまの取引先1社に、実際に取引して成果が出たかを直接確かめる');

  return {
    got: got.slice(0, 4),
    missing: missing.slice(0, 4),
    actions: actions.slice(0, 3),
  };
}

const google = query => `https://www.google.com/search?q=${encodeURIComponent(query)}`;
const LEGAL_FORMS = /株式会社|合同会社|有限会社|一般社団法人|一般財団法人|特定非営利活動法人/g;

// サイトの外は自動で調べない（2026-10-19 決定：Web検索は入れない）。
// かわりに、人が押すだけで済む検索リンクを、表記ゆれごとに組み立てる。
export function searchLinks(context = {}) {
  const corp = context.corporation || {};
  const rawName = String(corp.name || context.nameGuess || '').normalize('NFKC').trim();
  const bare = rawName.replace(LEGAL_FORMS, '').trim();
  const kana = String(corp.kana || '').trim();
  const rep = String(corp.representative || '').replace(/^(?:代表取締役|取締役|代表社員|代表理事|理事長|社長)[\s　]*(?:社長)?[\s　]*/, '').trim();
  const links = [];
  if (bare) {
    links.push({ label: `「${bare}」の評判・トラブルを検索`, url: google(`"${bare}" 評判 OR 口コミ OR トラブル`) });
    links.push({ label: `「${bare}」の SNS（X・Instagram・Facebook）を検索`, url: google(`"${bare}" (site:x.com OR site:instagram.com OR site:facebook.com)`) });
    links.push({ label: `「${bare}」の求人を検索（人数を名乗るのに求人の跡がないか）`, url: google(`"${bare}" 求人 OR 採用`) });
    if (kana && kana !== bare) links.push({ label: `ふりがな「${kana}」でも検索`, url: google(`"${kana}"`) });
  }
  if (rep && bare) links.push({ label: `代表者「${rep}」と社名で検索`, url: google(`"${rep}" "${bare}"`) });
  for (const phone of (context.phones || []).slice(0, 1)) {
    links.push({ label: `電話番号 ${phone} を検索（別の会社名で出てこないか）`, url: google(`"${phone}"`) });
  }
  if (corp.location) links.push({ label: '登記の住所を地図で見る（建物・部屋の実在）', url: `https://www.google.com/maps/search/${encodeURIComponent(corp.location)}` });
  return links;
}
