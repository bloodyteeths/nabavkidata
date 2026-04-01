#!/usr/bin/env python3
"""
Government & Donor Outreach Campaign — April 1, 2026
Sends personalized emails to 10 target organizations for the pivot from SaaS to
government/donor sales of procurement intelligence platform.

Uses Postmark Batch API (single call for all emails).

Usage:
  python3 send_government_outreach.py --dry-run          # Preview all emails
  python3 send_government_outreach.py --target dksk       # Preview one target
  python3 send_government_outreach.py --live              # Send all
  python3 send_government_outreach.py --target eu --live  # Send to one target
"""

import os
import sys
import json
import logging
import argparse
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

POSTMARK_API_TOKEN = os.getenv("POSTMARK_API_TOKEN", "33d10a6c-0906-42c6-ab14-441ad12b9e2a")
POSTMARK_BATCH_URL = "https://api.postmarkapp.com/email/batch"
FROM_EMAIL = "Атила Танрикулу, NabavkiData <hello@nabavkidata.com>"
DEMO_URL = "https://nabavkidata.com/transparency"

# ─────────────────────────────────────────────────────────────
# HTML TEMPLATE
# ─────────────────────────────────────────────────────────────

def build_html(body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background-color:#f4f4f7;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f7;padding:20px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;box-shadow:0 4px 6px rgba(0,0,0,0.1);overflow:hidden;">
  <tr><td style="background:linear-gradient(135deg,#1e40af 0%,#1d4ed8 100%);padding:30px 40px;text-align:left;">
    <div style="color:#93c5fd;font-size:14px;margin-bottom:8px;">NabavkiData</div>
    <div style="color:#ffffff;font-size:20px;font-weight:600;">Procurement Intelligence</div>
  </td></tr>
  <tr><td style="padding:32px 40px;color:#374151;font-size:15px;line-height:1.7;">
    {body_html}
  </td></tr>
  <tr><td style="padding:20px 40px;background:#f9fafb;border-top:1px solid #e5e7eb;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="font-size:12px;color:#9ca3af;">
        Фактурино ДООЕЛ &mdash; nabavkidata.com<br>
        hello@nabavkidata.com | +389 70 253 467
      </td>
    </tr></table>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""


# ─────────────────────────────────────────────────────────────
# EMAIL DEFINITIONS
# ─────────────────────────────────────────────────────────────

EMAILS = {
    "dksk": {
        "to": "contact@dksk.org.mk",
        "subject": "Систем за детекција на ризици во јавни набавки — бесплатен пилот за ДКСК",
        "body": build_html("""
<p>Почитувани,</p>
<p>Се обраќаме од Фактурино ДООЕЛ (<a href="https://nabavkidata.com" style="color:#2563eb;">nabavkidata.com</a>) — развивме AI систем за мониторинг и анализа на ризици во јавните набавки во Северна Македонија.</p>
<p>Системот моментално следи <strong>285.000+ тендери</strong> и автоматски детектира корупциски индикатори:</p>
<ul style="padding-left:20px;">
  <li><strong>73.581</strong> случај на единствен понудувач</li>
  <li><strong>8.893</strong> случаи на манипулација со прагови</li>
  <li><strong>1.063</strong> идентични понуди</li>
  <li><strong>4.340</strong> поврзани компании (ист сопственик, адреса, кластери на понуди)</li>
  <li><strong>2.597</strong> тендери со критично ниво на ризик</li>
</ul>
<p>Веруваме дека овој систем може значително да ја олесни работата на ДКСК при идентификација на сомнителни набавки.</p>
<p><strong>Нудиме бесплатен пилот проект (3 месеци)</strong> каде ќе ви обезбедиме:</p>
<ul style="padding-left:20px;">
  <li>Пристап до dashboard со ризик-скорови за сите активни тендери</li>
  <li>Неделни автоматски извештаи за најризични набавки</li>
  <li>Мапирање на мрежи од поврзани компании</li>
</ul>
<p><a href="{demo}" style="color:#2563eb;font-weight:600;">Погледнете ги податоците &rarr;</a></p>
<p>Дали можеме да закажеме краток состанок (15 мин) за демонстрација?</p>
<p>Со почит,<br><strong>Атила Танрикулу</strong><br>Фактурино ДООЕЛ</p>
""".replace("{demo}", DEMO_URL)),
    },

    "fitr": {
        "to": "info@fitr.mk",
        "subject": "Иновативен AI систем за транспарентност на јавни набавки — можност за грант",
        "body": build_html("""
<p>Почитувани,</p>
<p>Се обраќаме од Фактурино ДООЕЛ — развивме AI платформа за мониторинг на јавни набавки (<a href="https://nabavkidata.com" style="color:#2563eb;">nabavkidata.com</a>) која автоматски детектира корупциски ризици во <strong>285.000+ тендери</strong>.</p>
<p>Платформата користи:</p>
<ul style="padding-left:20px;">
  <li>Вештачка интелигенција (Gemini) за анализа на тендерска документација</li>
  <li>Векторско пребарување на <strong>78.000+ документи</strong> на македонски јазик</li>
  <li><strong>13 типови</strong> на корупциски индикатори со автоматска детекција</li>
  <li>Мапирање на мрежи од поврзани компании</li>
</ul>
<p>Заинтересирани сме за можностите за грантови од ФИТР за комерцијализација на овој производ, особено во категоријата GovTech / дигитална трансформација.</p>
<p>Дали постои отворен повик или можност за консултација за соодветниот инструмент?</p>
<p><a href="{demo}" style="color:#2563eb;font-weight:600;">Демо &rarr;</a></p>
<p>Со почит,<br><strong>Атила Танрикулу</strong><br>Фактурино ДООЕЛ</p>
""".replace("{demo}", DEMO_URL)),
    },

    "ccc": {
        "to": "center@ccc.org.mk",
        "subject": "Технолошко партнерство за мониторинг на јавни набавки",
        "body": build_html("""
<p>Почитувани г-дин Филков и г-ѓа Факиќ,</p>
<p>Го следиме вашиот долгогодишен мониторинг на јавните набавки и извештаите за транспарентност — вашата работа е исклучително важна за отчетноста на институциите.</p>
<p>Развивме AI систем (<a href="https://nabavkidata.com" style="color:#2563eb;">nabavkidata.com</a>) кој автоматски детектира корупциски ризици во <strong>285.000+ тендери</strong> од е-набавки. Системот идентификувал:</p>
<ul style="padding-left:20px;">
  <li><strong>124.501</strong> корупциски знаменца (13 типови индикатори)</li>
  <li><strong>73.581</strong> набавки со единствен понудувач</li>
  <li><strong>4.340</strong> поврзани компании (ист сопственик, адреса, заеднички понуди)</li>
</ul>
<p>Веруваме дека овој алат може да ја зајакне вашата аналитичка работа и да биде основа за заеднички грант-апликации (EU IPA, USAID, други донатори).</p>
<p><strong>Предлагаме:</strong></p>
<ul style="padding-left:20px;">
  <li>Бесплатен пристап до платформата за вашиот тим</li>
  <li>Заеднички настап кон донатори (ние = технологија, вие = институционален кредибилитет)</li>
  <li>Техничка поддршка за вашите истражувања</li>
</ul>
<p><a href="{demo}" style="color:#2563eb;font-weight:600;">Погледнете ги податоците &rarr;</a></p>
<p>Дали можеме да закажеме состанок?</p>
<p>Со почит,<br><strong>Атила Танрикулу</strong><br>Фактурино ДООЕЛ</p>
""".replace("{demo}", DEMO_URL)),
    },

    "ti": {
        "to": "info@transparency.mk",
        "subject": "AI систем за детекција на корупција во јавни набавки — партнерство",
        "body": build_html("""
<p>Почитувани,</p>
<p>Развивме AI систем (<a href="https://nabavkidata.com" style="color:#2563eb;">nabavkidata.com</a>) за автоматска детекција на корупциски ризици во јавните набавки во Северна Македонија.</p>
<p>Од <strong>285.000</strong> анализирани тендери, системот детектирал:</p>
<ul style="padding-left:20px;">
  <li><strong>124.501</strong> корупциски знаменца</li>
  <li><strong>2.597</strong> тендери со критично ниво на ризик</li>
  <li><strong>73.581</strong> набавки со единствен понудувач</li>
  <li><strong>4.340</strong> поврзани компании (споделен сопственик, адреса, кластери)</li>
</ul>
<p>Овие податоци се корисни за вашата advocacy работа и можат да бидат основа за заеднички проекти со донатори.</p>
<p><strong>Предлагаме:</strong></p>
<ul style="padding-left:20px;">
  <li>Бесплатен пристап до платформата за TI Macedonia</li>
  <li>Заеднички грант-апликации (EU, USAID)</li>
  <li>Споделување на податоци за ваши извештаи и кампањи</li>
</ul>
<p><a href="{demo}" style="color:#2563eb;font-weight:600;">Погледнете ги податоците &rarr;</a></p>
<p>Ве молиме јавете се ако сте заинтересирани за состанок.</p>
<p>Со почит,<br><strong>Атила Танрикулу</strong><br>Фактурино ДООЕЛ</p>
""".replace("{demo}", DEMO_URL)),
    },

    "metamorphosis": {
        "to": "info@metamorphosis.org.mk",
        "subject": "AI платформа за транспарентност на јавни набавки — соработка",
        "body": build_html("""
<p>Почитувани,</p>
<p>Развивме AI платформа (<a href="https://nabavkidata.com" style="color:#2563eb;">nabavkidata.com</a>) за мониторинг на јавните набавки во Северна Македонија. Системот автоматски детектира корупциски ризици во <strong>285.000+ тендери</strong> и анализира <strong>78.000+ тендерски документи</strong>.</p>
<p>Знаејќи ја вашата работа на дигитално управување и отворени податоци, веруваме дека постои простор за соработка:</p>
<ul style="padding-left:20px;">
  <li>Заеднички проекти за отворени податоци во јавните набавки</li>
  <li>Техничка основа за ваши истражувања и извештаи</li>
  <li>Партнерство за грант-апликации кај донатори</li>
</ul>
<p><a href="{demo}" style="color:#2563eb;font-weight:600;">Погледнете ги податоците &rarr;</a></p>
<p>Дали сте заинтересирани за состанок?</p>
<p>Со почит,<br><strong>Атила Танрикулу</strong><br>Фактурино ДООЕЛ</p>
""".replace("{demo}", DEMO_URL)),
    },

    "eu": {
        "to": "delegation-north-macedonia@eeas.europa.eu",
        "subject": "AI-Powered Procurement Transparency Tool for North Macedonia — Partnership Opportunity",
        "body": build_html("""
<p>Dear colleagues at the EU Delegation,</p>
<p>I am writing from Fakturino Dooel (<a href="https://nabavkidata.com" style="color:#2563eb;">nabavkidata.com</a>), a Macedonian tech company that has built an AI-powered procurement monitoring system for North Macedonia's public procurement.</p>
<p>Our system currently monitors <strong>285,000+ tenders</strong> from e-nabavki.gov.mk and automatically detects corruption risk indicators:</p>
<ul style="padding-left:20px;">
  <li><strong>124,501</strong> corruption flags across 13 indicator types</li>
  <li><strong>73,581</strong> single-bidder procurements detected</li>
  <li><strong>8,893</strong> threshold manipulation cases</li>
  <li><strong>4,340</strong> company relationships mapped (shared ownership, addresses, bid clustering)</li>
  <li><strong>2,597</strong> critical-risk tenders flagged</li>
</ul>
<p>This directly supports North Macedonia's EU accession priorities in public administration reform and Open Government Partnership commitments (particularly commitment 1.2 on beneficial ownership transparency).</p>
<p>We are seeking partnership opportunities within IPA III programs, particularly:</p>
<ul style="padding-left:20px;">
  <li>Public administration reform and governance projects</li>
  <li>Anti-corruption and rule of law initiatives</li>
  <li>Digital transformation of public services</li>
</ul>
<p>We offer a working, production-ready system with AI analysis in Macedonian language &mdash; not a concept or proposal, but a live tool with real data.</p>
<p><a href="{demo}" style="color:#2563eb;font-weight:600;">View live data &rarr;</a></p>
<p>Would it be possible to schedule a brief meeting to demonstrate the system?</p>
<p>Best regards,<br><strong>Atilla Tanrikulu</strong><br>Fakturino Dooel</p>
""".replace("{demo}", DEMO_URL)),
    },

    "worldbank": {
        "to": "abozinovska@worldbank.org",
        "subject": "Complementing North Macedonia's Red Flag System with AI Procurement Analytics",
        "body": build_html("""
<p>Dear World Bank North Macedonia team,</p>
<p>We are aware of the World Bank's Red Flag System pilot in North Macedonia, which has successfully flagged 40 high-risk procedures since January 2023 using 24 algorithmic indicators.</p>
<p>We have independently built a complementary system (<a href="https://nabavkidata.com" style="color:#2563eb;">nabavkidata.com</a>) that analyzes <strong>285,000+</strong> historical and active tenders with 13 corruption indicator types and has detected:</p>
<ul style="padding-left:20px;">
  <li><strong>124,501</strong> corruption flags</li>
  <li><strong>73,581</strong> single-bidder cases</li>
  <li><strong>4,340</strong> company relationship networks (shared ownership, addresses, bid clustering)</li>
  <li><strong>78,423</strong> tender documents analyzed with AI</li>
</ul>
<p>Our system adds capabilities beyond the current Red Flag System:</p>
<ul style="padding-left:20px;">
  <li>Company network mapping (detecting shell company clusters)</li>
  <li>AI-powered document analysis in Macedonian</li>
  <li>Historical trend analysis across 15+ years of procurement data</li>
  <li>Natural language search and investigation tools</li>
</ul>
<p>We would welcome the opportunity to discuss how our system could complement or integrate with the World Bank's ongoing procurement governance work in North Macedonia.</p>
<p><a href="{demo}" style="color:#2563eb;font-weight:600;">View live data &rarr;</a></p>
<p>Best regards,<br><strong>Atilla Tanrikulu</strong><br>Fakturino Dooel</p>
""".replace("{demo}", DEMO_URL)),
    },

    "osce": {
        "to": "info-mk@osce.org",
        "subject": "AI Procurement Transparency Tool — Supporting Rule of Law in North Macedonia",
        "body": build_html("""
<p>Dear OSCE Mission to Skopje,</p>
<p>We have developed an AI-powered procurement monitoring system (<a href="https://nabavkidata.com" style="color:#2563eb;">nabavkidata.com</a>) that automatically detects corruption risks in North Macedonia's public procurement.</p>
<p>Key capabilities:</p>
<ul style="padding-left:20px;">
  <li><strong>285,000+</strong> tenders monitored with automated risk scoring</li>
  <li><strong>13</strong> corruption indicator types (single-bidder, threshold manipulation, identical bids, etc.)</li>
  <li>Company relationship mapping (<strong>4,340</strong> connected entities detected)</li>
  <li>AI-powered document analysis in Macedonian language</li>
</ul>
<p>This tool supports the Mission's rule of law and democratic governance priorities by enabling data-driven oversight of public spending.</p>
<p>We are open to partnerships, pilot projects, or integration with existing OSCE governance programs in North Macedonia.</p>
<p><a href="{demo}" style="color:#2563eb;font-weight:600;">View live data &rarr;</a></p>
<p>Best regards,<br><strong>Atilla Tanrikulu</strong><br>Fakturino Dooel</p>
""".replace("{demo}", DEMO_URL)),
    },

    "giz": {
        "to": "giz-nordmazedonien@giz.de",
        "subject": "GovTech Solution for Procurement Transparency in North Macedonia",
        "body": build_html("""
<p>Dear GIZ North Macedonia team,</p>
<p>We have built an AI-powered procurement monitoring platform (<a href="https://nabavkidata.com" style="color:#2563eb;">nabavkidata.com</a>) for North Macedonia that automatically detects corruption risks across <strong>285,000+</strong> public tenders.</p>
<p>The system identifies single-bidder procurements, threshold manipulation, company relationship networks, and price anomalies &mdash; providing the kind of data-driven governance tool that supports EU accession reform priorities.</p>
<p>Key results:</p>
<ul style="padding-left:20px;">
  <li><strong>124,501</strong> corruption flags detected across 13 indicator types</li>
  <li><strong>4,340</strong> company relationships mapped</li>
  <li><strong>78,423</strong> tender documents analyzed with AI</li>
</ul>
<p>We are exploring partnership opportunities with development organizations active in Western Balkans governance reform. Would you be interested in a brief demonstration?</p>
<p><a href="{demo}" style="color:#2563eb;font-weight:600;">View live data &rarr;</a></p>
<p>Best regards,<br><strong>Atilla Tanrikulu</strong><br>Fakturino Dooel</p>
""".replace("{demo}", DEMO_URL)),
    },

    "birn": {
        "to": "ana@birn.eu.com",
        "subject": "Procurement Data Partnership for Investigative Journalism",
        "body": build_html("""
<p>Dear Ana,</p>
<p>We have built an AI-powered procurement monitoring system (<a href="https://nabavkidata.com" style="color:#2563eb;">nabavkidata.com</a>) that tracks <strong>285,000+</strong> public tenders in North Macedonia and automatically detects corruption indicators.</p>
<p>Our database includes:</p>
<ul style="padding-left:20px;">
  <li><strong>124,501</strong> corruption flags (single-bidder, threshold manipulation, identical bids)</li>
  <li><strong>4,340</strong> connected company relationships (shared owners, addresses, bid clusters)</li>
  <li><strong>78,423</strong> analyzed tender documents</li>
  <li><strong>2,597</strong> critical-risk tenders</li>
</ul>
<p>This data could be valuable for BIRN's investigative reporting on procurement in North Macedonia. We can provide:</p>
<ul style="padding-left:20px;">
  <li>Free access to our platform for BIRN journalists</li>
  <li>Custom data queries for specific investigations</li>
  <li>Company network maps showing ownership connections</li>
</ul>
<p><a href="{demo}" style="color:#2563eb;font-weight:600;">View live data &rarr;</a></p>
<p>Would you be interested in discussing a data partnership?</p>
<p>Best regards,<br><strong>Atilla Tanrikulu</strong><br>Fakturino Dooel</p>
""".replace("{demo}", DEMO_URL)),
    },
}


# ─────────────────────────────────────────────────────────────
# SENDING
# ─────────────────────────────────────────────────────────────

def build_postmark_message(key: str, email_def: dict) -> dict:
    return {
        "From": FROM_EMAIL,
        "To": email_def["to"],
        "Subject": email_def["subject"],
        "HtmlBody": email_def["body"],
        "MessageStream": "outbound",
        "TrackOpens": True,
        "TrackLinks": "HtmlAndText",
        "Tag": f"gov-outreach-{key}",
        "Metadata": {"campaign": "government-outreach-apr2026", "target": key},
    }


def main():
    parser = argparse.ArgumentParser(description="Government & Donor Outreach Campaign")
    parser.add_argument("--live", action="store_true", help="Actually send emails (default: dry run)")
    parser.add_argument("--target", type=str, help="Send to specific target only (e.g., dksk, eu, birn)")
    args = parser.parse_args()

    targets = {args.target: EMAILS[args.target]} if args.target else EMAILS

    if args.target and args.target not in EMAILS:
        logger.error(f"Unknown target: {args.target}. Available: {', '.join(EMAILS.keys())}")
        sys.exit(1)

    messages = []
    for key, email_def in targets.items():
        msg = build_postmark_message(key, email_def)
        messages.append(msg)
        logger.info(f"{'SEND' if args.live else 'DRY-RUN'} [{key}] → {email_def['to']}")
        logger.info(f"  Subject: {email_def['subject']}")

    if not args.live:
        logger.info(f"\n{'='*60}")
        logger.info(f"DRY RUN — {len(messages)} emails prepared. Use --live to send.")
        logger.info(f"{'='*60}")
        for msg in messages:
            print(f"\n--- {msg['Tag']} ---")
            print(f"To: {msg['To']}")
            print(f"Subject: {msg['Subject']}")
            print(f"From: {msg['From']}")
            print()
        return

    # Send via Postmark Batch API
    logger.info(f"\nSending {len(messages)} emails via Postmark Batch API...")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": POSTMARK_API_TOKEN,
    }

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(POSTMARK_BATCH_URL, headers=headers, json=messages)

    if resp.status_code == 200:
        results = resp.json()
        for i, result in enumerate(results):
            key = list(targets.keys())[i]
            if result.get("ErrorCode", 0) == 0:
                logger.info(f"  ✓ [{key}] → {result.get('To', '?')} — MessageID: {result.get('MessageID', '?')}")
            else:
                logger.error(f"  ✗ [{key}] → Error {result.get('ErrorCode')}: {result.get('Message', '?')}")
    else:
        logger.error(f"Batch API failed: {resp.status_code} — {resp.text}")
        sys.exit(1)

    logger.info(f"\nDone! {len(messages)} emails sent.")


if __name__ == "__main__":
    main()
