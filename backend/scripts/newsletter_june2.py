#!/usr/bin/env python3
"""
Newsletter: Тендер Билтен — Јуни 2026
Sends to ~23K MK business contacts via Postmark broadcast stream.
Schedule: Monday June 2, 2026 at 09:00 Skopje time (07:00 UTC)
"""

import asyncio
import asyncpg
import httpx
import time
import argparse
import json
from datetime import datetime

POSTMARK_TOKEN = "97e9c355-08fc-4ef0-85b7-c3243b1bd330"
POSTMARK_URL = "https://api.postmarkapp.com/email"
FROM_EMAIL = "hello@nabavkidata.com"
SUBJECT = "е-Фактура задолжителна од октомври · €3.3 милијарди инфраструктурни проекти · Тендер Билтен"
DB_DSN = "postgresql://nabavki_user:N4bavk1H3tzn3r2026!Secure@localhost:5432/nabavkidata"
BATCH_SIZE = 50
BATCH_DELAY = 1.5  # seconds between batches

NEWSLETTER_HTML = """<!DOCTYPE html>
<html lang="mk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Тендер Билтен — Јуни 2026</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f7;font-family:Arial,Helvetica,sans-serif;">
<div style="max-width:620px;margin:0 auto;background:#ffffff;">

<!-- Header -->
<div style="background:#1e3a5f;padding:28px 32px;text-align:center;">
  <h1 style="color:#ffffff;font-size:22px;margin:0 0 4px 0;font-weight:700;">ТЕНДЕР БИЛТЕН</h1>
  <p style="color:#8bb8e8;font-size:13px;margin:0;">Јуни 2026 · NabavkiData.com</p>
</div>

<!-- Intro -->
<div style="padding:28px 32px 20px;">
  <p style="font-size:15px;line-height:1.6;color:#333;margin:0 0 16px 0;">
    Добар ден,
  </p>
  <p style="font-size:15px;line-height:1.6;color:#333;margin:0 0 16px 0;">
    Ова е првиот број на <strong>Тендер Билтен</strong> — месечен преглед на најважните случувања во јавните набавки што директно влијаат на вашиот бизнис. Без реклами, само информации што вредат.
  </p>
</div>

<!-- STORY 1: e-Faktura -->
<div style="padding:0 32px 24px;">
  <div style="background:#fff3cd;border-left:4px solid #ffc107;padding:16px 20px;border-radius:0 8px 8px 0;">
    <p style="font-size:11px;font-weight:700;color:#856404;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:1px;">Важен рок</p>
    <h2 style="font-size:18px;color:#333;margin:0 0 10px 0;">е-Фактура задолжителна од 1 октомври 2026</h2>
    <p style="font-size:14px;line-height:1.6;color:#555;margin:0 0 10px 0;">
      Сите ДДВ обврзници (фирми со годишен промет над 1.000.000 ден) <strong>мора да преминат на електронско фактурирање</strong> преку системот на УЈП до 1 октомври.
    </p>
    <p style="font-size:14px;line-height:1.6;color:#555;margin:0 0 10px 0;">
      Фактурите ќе бидат во XML/UBL формат со дигитален потпис. УЈП ќе ги вкрстува сите трансакции во реално време.
    </p>
    <p style="font-size:14px;line-height:1.6;color:#555;margin:0 0 12px 0;">
      <strong>Што треба да направите:</strong> Проверете дали вашиот сметководствен софтвер поддржува е-Фактура. Пилот тестирањето е веќе активно.
    </p>
    <p style="font-size:14px;line-height:1.6;color:#555;margin:0;">
      Нашиот тим го развива <a href="https://facturino.mk?utm_source=newsletter&utm_medium=email&utm_campaign=june2026" style="color:#1e3a5f;font-weight:600;text-decoration:underline;">Facturino.mk</a> — едноставна платформа за електронско фактурирање усогласена со барањата на УЈП. Бесплатен пробен период, без обврска. Проверете дали е вистинското решение за вас.
    </p>
    <p style="margin:12px 0 0 0;"><a href="https://www.nabavkidata.com/blog/e-faktura-zadolzhitelna-oktomvri-2026?utm_source=newsletter&utm_medium=email&utm_campaign=june2026" style="color:#1e3a5f;font-size:13px;font-weight:600;text-decoration:none;">Прочитајте повеќе &rarr;</a></p>
  </div>
</div>

<!-- STORY 2: Infrastructure -->
<div style="padding:0 32px 24px;">
  <h2 style="font-size:18px;color:#1e3a5f;margin:0 0 12px 0;border-bottom:2px solid #e8e8e8;padding-bottom:8px;">€3.3 милијарди за инфраструктура во наредните 5 години</h2>
  <p style="font-size:14px;line-height:1.6;color:#555;margin:0 0 12px 0;">
    На 29 април се одржа првата седница на новиот <strong>Комитет за јавни инвестиции</strong> при Министерството за финансии. Секој проект над €5 милиони мора да помине преку овој комитет. Вкупниот план: <strong>над €600 милиони годишно</strong> само во градежништво.
  </p>
  <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">
    <tr style="background:#f0f4f8;">
      <td style="padding:10px 12px;font-size:13px;color:#333;border-bottom:1px solid #e0e0e0;"><strong>Договор со В. Британија</strong></td>
      <td style="padding:10px 12px;font-size:13px;color:#1e3a5f;border-bottom:1px solid #e0e0e0;text-align:right;"><strong>€6 милијарди</strong></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;font-size:13px;color:#555;border-bottom:1px solid #e0e0e0;">3 болници (Штип, Тетово, Кичево)</td>
      <td style="padding:10px 12px;font-size:13px;color:#1e3a5f;border-bottom:1px solid #e0e0e0;text-align:right;">€205 милиони</td>
    </tr>
    <tr style="background:#f0f4f8;">
      <td style="padding:10px 12px;font-size:13px;color:#555;border-bottom:1px solid #e0e0e0;">Железница Коридор 10</td>
      <td style="padding:10px 12px;font-size:13px;color:#1e3a5f;border-bottom:1px solid #e0e0e0;text-align:right;">€2 милијарди</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;font-size:13px;color:#555;border-bottom:1px solid #e0e0e0;">829 локални проекти низ општините</td>
      <td style="padding:10px 12px;font-size:13px;color:#1e3a5f;border-bottom:1px solid #e0e0e0;text-align:right;">15 млрд ден</td>
    </tr>
    <tr style="background:#f0f4f8;">
      <td style="padding:10px 12px;font-size:13px;color:#555;border-bottom:1px solid #e0e0e0;">145 училишни спортски сали</td>
      <td style="padding:10px 12px;font-size:13px;color:#1e3a5f;border-bottom:1px solid #e0e0e0;text-align:right;">2026-2029</td>
    </tr>
  </table>
  <p style="font-size:13px;line-height:1.5;color:#888;margin:0;">
    Градежништвото е на прво место по вредност — изминатиот месец објавени се 221 тендер во вредност од 1.67 милијарди денари.
  </p>
  <p style="margin:12px 0 0 0;"><a href="https://www.nabavkidata.com/blog/infrastrukturni-proekti-33-milijardi-2026?utm_source=newsletter&utm_medium=email&utm_campaign=june2026" style="color:#1e3a5f;font-size:13px;font-weight:600;text-decoration:none;">Прочитајте повеќе &rarr;</a></p>
</div>

<!-- STORY 3: EU Funds -->
<div style="padding:0 32px 24px;">
  <h2 style="font-size:18px;color:#1e3a5f;margin:0 0 12px 0;border-bottom:2px solid #e8e8e8;padding-bottom:8px;">ЕУ одобри €65.7 милиони за Македонија (20 мај)</h2>
  <p style="font-size:14px;line-height:1.6;color:#555;margin:0 0 12px 0;">
    Европската комисија пушти <strong>€65.7 милиони</strong> од Планот за раст — <strong>највисок износ во регионот</strong>. Парите одат за:
  </p>
  <ul style="font-size:14px;line-height:1.8;color:#555;margin:0 0 12px 0;padding-left:20px;">
    <li><strong>€30.6М</strong> — директна буџетска поддршка за образование и ИТ опрема за 160 основни училишта</li>
    <li>Инвестициски проекти во транспорт, енергетика и дигитализација</li>
    <li>ЕБРД зелен кредит од <strong>€30М</strong> за МСП преку НЛБ — за одржливи технологии</li>
  </ul>
  <p style="font-size:13px;line-height:1.5;color:#888;margin:0;">
    Вкупно до сега исплатени €142 милиони од алокирани €750 милиони (2024-2027).
  </p>
  <p style="margin:12px 0 0 0;"><a href="https://www.nabavkidata.com/blog/eu-65-milioni-plan-za-rast-2026?utm_source=newsletter&utm_medium=email&utm_campaign=june2026" style="color:#1e3a5f;font-size:13px;font-weight:600;text-decoration:none;">Прочитајте повеќе &rarr;</a></p>
</div>

<!-- STORY 4: Budget Rebalance -->
<div style="padding:0 32px 24px;">
  <h2 style="font-size:18px;color:#1e3a5f;margin:0 0 12px 0;border-bottom:2px solid #e8e8e8;padding-bottom:8px;">Ребаланс на буџетот во јуни/јули — нови тендери на повидок</h2>
  <p style="font-size:14px;line-height:1.6;color:#555;margin:0 0 12px 0;">
    Премиерот најави ребаланс на буџетот кој ќе биде подготвен во јуни и испратен до Собрание. Министерството за финансии веќе побара податоци од сите институции за капитални инвестиции.
  </p>
  <p style="font-size:14px;line-height:1.6;color:#555;margin:0;">
    <strong>Што значи ова:</strong> Ребалансот носи нови алокации за капитални проекти = нови тендери во втората половина од 2026. Подгответе ја документацијата сега.
  </p>
  <p style="margin:12px 0 0 0;"><a href="https://www.nabavkidata.com/blog/rebalans-budzet-juni-2026?utm_source=newsletter&utm_medium=email&utm_campaign=june2026" style="color:#1e3a5f;font-size:13px;font-weight:600;text-decoration:none;">Прочитајте повеќе &rarr;</a></p>
</div>

<!-- STORY 5: Renewables -->
<div style="padding:0 32px 24px;">
  <h2 style="font-size:18px;color:#1e3a5f;margin:0 0 12px 0;border-bottom:2px solid #e8e8e8;padding-bottom:8px;">Обновлива енергија: 4.4 GW, €3.7 милијарди</h2>
  <p style="font-size:14px;line-height:1.6;color:#555;margin:0 0 12px 0;">
    Од 284 поднесени апликации, <strong>67 се одобрени</strong> за објекти над 1 MW:
  </p>
  <ul style="font-size:14px;line-height:1.8;color:#555;margin:0 0 12px 0;padding-left:20px;">
    <li>59 соларни централи — 3 GW, ~€2.1 милијарди</li>
    <li>7 ветерни паркови — 907 MW, ~€1.1 милијарда</li>
  </ul>
  <p style="font-size:14px;line-height:1.6;color:#555;margin:0;">
    Компаниите од енергетскиот сектор, инсталатери и добавувачи на опрема имаат историска можност.
  </p>
  <p style="margin:12px 0 0 0;"><a href="https://www.nabavkidata.com/blog/obnovliva-energija-44gw-2026?utm_source=newsletter&utm_medium=email&utm_campaign=june2026" style="color:#1e3a5f;font-size:13px;font-weight:600;text-decoration:none;">Прочитајте повеќе &rarr;</a></p>
</div>

<!-- STORY 6: Legal Changes -->
<div style="padding:0 32px 24px;">
  <div style="background:#e8f4fd;border-left:4px solid #2196F3;padding:16px 20px;border-radius:0 8px 8px 0;">
    <p style="font-size:11px;font-weight:700;color:#1565c0;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:1px;">Правни промени</p>
    <h2 style="font-size:16px;color:#333;margin:0 0 10px 0;">Нова Државна комисија за жалби + Нов Закон за јавни набавки во подготовка</h2>
    <p style="font-size:14px;line-height:1.6;color:#555;margin:0 0 8px 0;">
      Државната комисија за жалби е во нов состав. Електронско поднесување жалби преку ЕСЈН е овозможено.
    </p>
    <p style="font-size:14px;line-height:1.6;color:#555;margin:0;">
      Министерството за финансии подготвува целосно <strong>нов Закон за јавни набавки</strong> — следете ги промените бидејќи ќе влијаат на процедурите за сите понудувачи.
    </p>
    <p style="margin:12px 0 0 0;"><a href="https://www.nabavkidata.com/blog/nov-zakon-javni-nabavki-2026?utm_source=newsletter&utm_medium=email&utm_campaign=june2026" style="color:#1e3a5f;font-size:13px;font-weight:600;text-decoration:none;">Прочитајте повеќе &rarr;</a></p>
  </div>
</div>

<!-- Quick stats -->
<div style="padding:0 32px 24px;">
  <h2 style="font-size:18px;color:#1e3a5f;margin:0 0 12px 0;border-bottom:2px solid #e8e8e8;padding-bottom:8px;">Мај 2026 во бројки</h2>
  <table style="width:100%;border-collapse:collapse;">
    <tr>
      <td style="padding:12px 16px;text-align:center;background:#1e3a5f;border-radius:8px 0 0 0;">
        <p style="font-size:22px;font-weight:700;color:#fff;margin:0;">3,508</p>
        <p style="font-size:11px;color:#8bb8e8;margin:4px 0 0 0;">нови тендери</p>
      </td>
      <td style="padding:12px 16px;text-align:center;background:#2a4a6f;">
        <p style="font-size:22px;font-weight:700;color:#fff;margin:0;">+25%</p>
        <p style="font-size:11px;color:#8bb8e8;margin:4px 0 0 0;">раст од април</p>
      </td>
      <td style="padding:12px 16px;text-align:center;background:#1e3a5f;border-radius:0 8px 0 0;">
        <p style="font-size:22px;font-weight:700;color:#fff;margin:0;">2,317</p>
        <p style="font-size:11px;color:#8bb8e8;margin:4px 0 0 0;">отворени сега</p>
      </td>
    </tr>
  </table>
</div>

<!-- CTA -->
<div style="padding:0 32px 28px;">
  <div style="background:#f0f7ff;border-radius:12px;padding:24px;text-align:center;">
    <h3 style="font-size:17px;color:#1e3a5f;margin:0 0 10px 0;">Пронајдете ги тендерите за вашата индустрија</h3>
    <p style="font-size:14px;color:#555;margin:0 0 16px 0;">
      NabavkiData следи 290,000+ тендери од е-набавки.гов.мк<br>Поставете аларм и добивајте известување кога ќе се објави нов тендер.
    </p>
    <a href="https://www.nabavkidata.com/auth/register?utm_source=newsletter&utm_medium=email&utm_campaign=june2026" style="display:inline-block;background:#1e3a5f;color:#ffffff;padding:12px 28px;border-radius:8px;text-decoration:none;font-size:14px;font-weight:600;">
      Бесплатна регистрација
    </a>
    <p style="font-size:12px;color:#999;margin:10px 0 0 0;">Без кредитна картичка. Поставете аларм за 2 минути.</p>
  </div>
</div>

<!-- Footer -->
<div style="background:#f4f4f7;padding:20px 32px;border-top:1px solid #e0e0e0;">
  <p style="font-size:12px;color:#999;margin:0 0 8px 0;text-align:center;">
    Тендер Билтен од <a href="https://www.nabavkidata.com?utm_source=newsletter&utm_medium=email&utm_campaign=june2026" style="color:#1e3a5f;text-decoration:none;">NabavkiData.com</a> — платформа за следење на јавни набавки
  </p>
  <p style="font-size:12px;color:#999;margin:0 0 8px 0;text-align:center;">
    Фактурино ДООЕЛ · Скопје, Македонија · +389 70 253 467
  </p>
  <p style="font-size:11px;color:#bbb;margin:0;text-align:center;">
    <a href="{{{pm:unsubscribe}}}" style="color:#999;text-decoration:underline;">Одјавете се од билтенот</a>
  </p>
</div>

</div>
</body>
</html>"""


async def get_recipients(pool, include_fresh=True):
    """Get all mailable contacts."""
    # Get suppressed emails (bounced + unsubscribed)
    suppressed = set()
    rows = await pool.fetch("""
        SELECT DISTINCT LOWER(email) FROM outreach_leads
        WHERE outreach_status IN ('bounced', 'unsubscribed')
        OR is_bounced = true
        OR unsubscribed_at IS NOT NULL
    """)
    for r in rows:
        suppressed.add(r[0])

    rows = await pool.fetch("SELECT DISTINCT LOWER(email) FROM suppression_list WHERE email IS NOT NULL")
    for r in rows:
        suppressed.add(r[0])

    rows = await pool.fetch("""
        SELECT DISTINCT LOWER(email) FROM campaign_unsubscribes WHERE email IS NOT NULL
    """)
    for r in rows:
        suppressed.add(r[0])

    # Get all mailable contacts from outreach_leads
    recipients = {}
    rows = await pool.fetch("""
        SELECT email, COALESCE(first_name, full_name, company_name, '') as name
        FROM outreach_leads
        WHERE email IS NOT NULL AND email != ''
    """)
    for r in rows:
        email_lower = r['email'].lower().strip()
        if email_lower not in suppressed and '@' in email_lower:
            recipients[email_lower] = r['name'] or ''

    if include_fresh:
        # Add fresh contacts from mk_companies
        rows = await pool.fetch("""
            SELECT email, COALESCE(name, '') as name
            FROM mk_companies
            WHERE email IS NOT NULL AND email != ''
        """)
        for r in rows:
            email_lower = r['email'].lower().strip()
            if email_lower not in suppressed and email_lower not in recipients and '@' in email_lower:
                recipients[email_lower] = r['name'] or ''

        # Add from apollo_contacts
        rows = await pool.fetch("""
            SELECT email, COALESCE(first_name, '') as name
            FROM apollo_contacts
            WHERE email IS NOT NULL AND email != ''
        """)
        for r in rows:
            email_lower = r['email'].lower().strip()
            if email_lower not in suppressed and email_lower not in recipients and '@' in email_lower:
                recipients[email_lower] = r['name'] or ''

        # Add from supplier_contacts
        rows = await pool.fetch("""
            SELECT email, COALESCE(contact_name, '') as name
            FROM supplier_contacts
            WHERE email IS NOT NULL AND email != ''
        """)
        for r in rows:
            email_lower = r['email'].lower().strip()
            if email_lower not in suppressed and email_lower not in recipients and '@' in email_lower:
                recipients[email_lower] = r['name'] or ''

    return recipients


async def send_email(client, email, name):
    """Send a single newsletter email via Postmark broadcast."""
    try:
        resp = await client.post(
            POSTMARK_URL,
            headers={
                "X-Postmark-Server-Token": POSTMARK_TOKEN,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "From": f"NabavkiData <{FROM_EMAIL}>",
                "To": email,
                "Subject": SUBJECT,
                "HtmlBody": NEWSLETTER_HTML,
                "MessageStream": "broadcast",
                "TrackOpens": True,
                "TrackLinks": "HtmlOnly",
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return "sent"
        else:
            data = resp.json()
            error_code = data.get("ErrorCode", 0)
            # 406 = inactive recipient, 300 = invalid email
            if error_code in (406, 300):
                return "inactive"
            print(f"  FAIL {email}: {resp.status_code} {data.get('Message', '')}")
            return "failed"
    except Exception as e:
        print(f"  ERROR {email}: {e}")
        return "error"


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Actually send emails")
    parser.add_argument("--preview", type=str, help="Send preview to this email")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of recipients")
    parser.add_argument("--no-fresh", action="store_true", help="Only send to existing outreach_leads")
    args = parser.parse_args()

    pool = await asyncpg.create_pool(DB_DSN, min_size=2, max_size=5)

    if args.preview:
        print(f"Sending preview to {args.preview}...")
        async with httpx.AsyncClient() as client:
            result = await send_email(client, args.preview, "Preview")
            print(f"Result: {result}")
        await pool.close()
        return

    recipients = await get_recipients(pool, include_fresh=not args.no_fresh)
    print(f"Total recipients: {len(recipients)}")

    if args.limit:
        emails = list(recipients.items())[:args.limit]
    else:
        emails = list(recipients.items())

    if not args.live:
        print("\nDRY RUN — add --live to actually send")
        print(f"Would send to {len(emails)} recipients")
        print(f"First 10: {[e[0] for e in emails[:10]]}")
        await pool.close()
        return

    print(f"\nSending to {len(emails)} recipients...")
    sent = 0
    failed = 0
    inactive = 0
    errors = 0

    async with httpx.AsyncClient() as client:
        for i in range(0, len(emails), BATCH_SIZE):
            batch = emails[i:i + BATCH_SIZE]
            tasks = [send_email(client, email, name) for email, name in batch]
            results = await asyncio.gather(*tasks)

            for result in results:
                if result == "sent":
                    sent += 1
                elif result == "inactive":
                    inactive += 1
                elif result == "failed":
                    failed += 1
                else:
                    errors += 1

            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(emails) + BATCH_SIZE - 1) // BATCH_SIZE
            print(f"  Batch {batch_num}/{total_batches}: sent={sent} inactive={inactive} failed={failed} errors={errors}")

            if i + BATCH_SIZE < len(emails):
                await asyncio.sleep(BATCH_DELAY)

    print(f"\nDone: {sent} sent, {inactive} inactive, {failed} failed, {errors} errors")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
