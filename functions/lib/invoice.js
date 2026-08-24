// 国税庁「適格請求書発行事業者公表システム」Web-API（Ver.1）の照会。
// GET /1/num?id=<アプリケーションID>&number=T+法人番号13桁&type=21（JSON）&history=0（最新のみ）
//
// 判定しない原則: 公表データにある事実だけを返す。事業者処理区分（process）と人格区分（kind）は
// コード表を実測できていないため解釈せず、値も外へ出さない。
// fail closed: IDが未設定・応答が壊れている・照会した番号が応答に無いときは「登録なし」に変換せず
// blocked として返す。「公表システムに存在しない」と言えるのは、正常な応答で件数0だったときだけ。

const ENDPOINT = 'https://web-api.invoice-kohyo.nta.go.jp/1/num';
const TIMEOUT_MS = 6000;
// WorkersのfetchはUser-Agentを付けない。国税庁側はUA無しの要求を403で拒否するため、
// 名乗りを明示する。これを外すと本番だけが「取得失敗」になり、ローカルでは再現しない。
const USER_AGENT = 'NGraph-vendor-check/1.0 (+https://ngraph.jp/check/)';

const text = value => (value == null ? '' : String(value).trim());

export function registrationNumberFor(corporateNumber) {
  const digits = text(corporateNumber).replace(/[^0-9]/g, '');
  return /^\d{13}$/.test(digits) ? `T${digits}` : null;
}

export function invoiceRequestUrl(number, appId) {
  return `${ENDPOINT}?id=${encodeURIComponent(appId)}&number=${number}&type=21&history=0`;
}

export async function lookupInvoiceRegistration(corporateNumber, appId, fetchImpl = globalThis.fetch) {
  const number = registrationNumberFor(corporateNumber);
  const blocked = stop_reason =>
    ({ number, status: 'blocked', stop_reason, registered: null, entry: null, lastUpdateDate: null });
  if (!number) return blocked('invalid_corporate_number');
  if (!appId) return blocked('app_id_not_configured');

  let response;
  try {
    response = await fetchImpl(invoiceRequestUrl(number, appId), {
      headers: { Accept: 'application/json', 'User-Agent': USER_AGENT },
      signal: typeof AbortSignal?.timeout === 'function' ? AbortSignal.timeout(TIMEOUT_MS) : undefined,
    });
  } catch {
    return blocked('network_error');
  }
  if (!response?.ok) return blocked(`http_${response?.status ?? 'no_response'}`);

  let data;
  try { data = await response.json(); } catch { return blocked('invalid_response'); }
  const list = Array.isArray(data?.announcement) ? data.announcement : null;
  if (!list) return blocked('invalid_response');

  const lastUpdateDate = text(data.lastUpdateDate) || null;
  if (!list.length) {
    return { number, status: 'covered', stop_reason: 'required_sources_exhausted',
      registered: false, entry: null, lastUpdateDate };
  }

  // 照会した登録番号以外が混ざった応答は、別法人の情報を貼り付ける事故になるので採用しない。
  const found = list.find(item => text(item?.registratedNumber).toUpperCase() === number);
  if (!found) return blocked('number_not_in_response');

  const disposalDate = text(found.disposalDate);
  const expireDate = text(found.expireDate);
  return {
    number,
    status: 'covered',
    stop_reason: 'required_sources_exhausted',
    registered: true,
    lastUpdateDate,
    entry: {
      registrationDate: text(found.registrationDate) || null,
      updateDate: text(found.updateDate) || null,
      disposalDate: disposalDate || null,
      expireDate: expireDate || null,
      // 個人事業者は氏名・所在地が非公表のことがあり、屋号や公表申出の住所だけが載る。
      name: text(found.name) || text(found.tradeName) || null,
      address: text(found.address) || text(found.addressRequest) || null,
      latest: text(found.latest) === '1',
      active: !disposalDate && !expireDate,
    },
  };
}
