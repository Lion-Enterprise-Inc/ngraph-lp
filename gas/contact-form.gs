/**
 * NGraph お問い合わせフォーム受信 GAS Web アプリ
 *
 * デプロイ手順:
 *  1. https://script.google.com を shingotakahashi@ngraph.jp アカウントで開く
 *  2. 新しいプロジェクト → このコードを「コード.gs」に貼り付け
 *  3. デプロイ → 新しいデプロイ → 種類「ウェブアプリ」
 *       - 実行するユーザー: 自分 (shingotakahashi@ngraph.jp)
 *       - アクセスできるユーザー: 全員
 *  4. 発行された https://script.google.com/macros/s/XXXX/exec を控える
 *  5. その URL を entry.html / en/entry.html の form action に差し込む
 *
 * OmiseAI の事前申し込み GAS と同方式 (no-cors POST → MailApp 自アカウント送信)。
 * formsubmit.co のアクティベーション依存をなくし、確実に受信箱へ届かせる。
 */

var TO = 'shingotakahashi@ngraph.jp';

function doPost(e) {
  try {
    var p = (e && e.parameter) ? e.parameter : {};

    // honeypot: bot が埋めたら静かに成功扱いで破棄
    if (p._honey) {
      return ContentService.createTextOutput('ok');
    }

    var name    = p['お名前'] || p['Name'] || '';
    var company = p['会社名・店舗名'] || p['Company / Store'] || '';
    var email   = p['メールアドレス'] || p['Email'] || '';
    var type    = p['お問い合わせ種別'] || p['Type of inquiry'] || '(未選択)';
    var message = p['お問い合わせ内容'] || p['Message'] || '';

    var lines = [
      'お名前: ' + name,
      '会社名・店舗名: ' + company,
      'メールアドレス: ' + email,
      'お問い合わせ種別: ' + type,
      '',
      'お問い合わせ内容:',
      message,
      '',
      '---',
      '送信日時: ' + Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd HH:mm:ss'),
      '送信元: ngraph.jp/entry'
    ];

    // 1) 自分への通知
    MailApp.sendEmail({
      to: TO,
      subject: 'NGraph お問い合わせ: ' + (company || name || '(無題)'),
      body: lines.join('\n'),
      replyTo: email || TO
    });

    // 2) 送信者への自動返信 (メールアドレスがある場合のみ)
    if (email && /@/.test(email)) {
      MailApp.sendEmail({
        to: email,
        subject: 'お問い合わせありがとうございます — 株式会社NGraph',
        body: [
          (name || 'ご担当者') + ' 様',
          '',
          'お問い合わせいただきありがとうございます。株式会社NGraphです。',
          '内容を確認の上、担当者より2〜3営業日以内にご連絡いたします。',
          '今しばらくお待ちください。',
          '',
          '--------------------',
          'いただいた内容:',
          message,
          '--------------------',
          '',
          '株式会社NGraph',
          'https://ngraph.jp'
        ].join('\n')
      });
    }

    return ContentService.createTextOutput('ok');
  } catch (err) {
    return ContentService.createTextOutput('error: ' + err);
  }
}
