#!/usr/bin/env python3
"""
Send tailored PR pitches to all channels:
- Tech/Startup blogs
- Government bodies
- Academic/Research
- International platforms
- Forums
"""
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

POSTMARK_API_TOKEN = "33d10a6c-0906-42c6-ab14-441ad12b9e2a"
FROM_NAME = "Тамара Сарсевска"
FROM_EMAIL = "hello@nabavkidata.com"

# ============================================================
# TEMPLATES
# ============================================================

TECH_BLOG_SUBJECT = "Македонски AI стартап за детекција на корупција во јавни набавки - приказна за вашиот портал"
TECH_BLOG_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Georgia, serif; font-size:16px; line-height:1.8; color:#1a1a1a;">
<div style="max-width:640px; margin:0 auto;">

<p>Здраво,</p>

<p>Ви пишувам од <strong>НабавкиДата</strong> (<a href="https://nabavkidata.com" style="color:#1a5276;">nabavkidata.com</a>) - македонски стартап кој користи AI за анализа на јавни набавки и детекција на корупција.</p>

<p>&nbsp;</p>

<p><strong>Што изградивме:</strong></p>
<ul style="padding-left:20px;">
<li>AI систем кој анализира <strong>15,000+ тендери</strong> со <strong>50+ индикатори за ризик</strong></li>
<li>Базиран на методологии на Светска Банка, OECD и украинскиот Dozorro</li>
<li>Автоматски открива: наместени тендери, ценовни аномалии, повторливи победници, поврзани компании</li>
<li>Веќе го користат <strong>4,500+ компании и граѓани</strong></li>
</ul>

<p>&nbsp;</p>

<p><strong>Зошто е ова интересно за вашата публика:</strong></p>
<ul style="padding-left:20px;">
<li>Прв AI систем за детекција на корупција во регионот</li>
<li>Изграден без државна поддршка - целосно приватна иницијатива</li>
<li>Користи машинско учење и NLP за анализа на документи</li>
<li>RAG (Retrieval-Augmented Generation) за интелигентно пребарување</li>
<li>Gemini embeddings за семантичко пребарување на тендери</li>
</ul>

<p>&nbsp;</p>

<p><strong>Технички стек:</strong> Next.js, FastAPI, PostgreSQL, Scrapy + Playwright, Gemini AI, Python ML pipeline</p>

<p>&nbsp;</p>

<p>Дали би биле заинтересирани за статија/приказна за ова? Можеме да обезбедиме:</p>
<ul style="padding-left:20px;">
<li>Детален технички преглед на системот</li>
<li>Демо на AI детекцијата во живо</li>
<li>Интервју со тимот</li>
<li>Конкретни примери на откриени аномалии</li>
</ul>

<p>&nbsp;</p>

<p>Јавете се на +389 70 253 467 или одговорете на овој мејл.</p>

<p>&nbsp;</p>

<p>Поздрав,</p>
<p><strong>Тамара Сарсевска</strong><br>НабавкиДата<br>hello@nabavkidata.com<br><a href="https://nabavkidata.com" style="color:#1a5276;">nabavkidata.com</a></p>

<hr style="border:none; border-top:1px solid #eee; margin:30px 0;">
<p style="font-size:12px; color:#999;">TAMSAR INC | 131 Continental Dr Ste 305, New Castle, DE 19713</p>
</div></body></html>"""


TECH_BLOG_EN_SUBJECT = "Macedonian AI Startup Detects Corruption in Public Procurement - Story Pitch"
TECH_BLOG_EN_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Georgia, serif; font-size:16px; line-height:1.8; color:#1a1a1a;">
<div style="max-width:640px; margin:0 auto;">

<p>Hi,</p>

<p>I'm reaching out from <strong>NabavkiData</strong> (<a href="https://nabavkidata.com" style="color:#1a5276;">nabavkidata.com</a>) - a Macedonian civic tech startup that uses AI to analyze public procurement and detect corruption patterns.</p>

<p>&nbsp;</p>

<p><strong>What we built:</strong></p>
<ul style="padding-left:20px;">
<li>AI system analyzing <strong>15,000+ government tenders</strong> with <strong>50+ risk indicators</strong></li>
<li>Based on World Bank, OECD, and Ukraine's Dozorro methodology</li>
<li>Automatically flags: rigged tenders, price anomalies, repeat winners, connected companies, bid clustering</li>
<li>Already used by <strong>4,500+ companies and citizens</strong> in North Macedonia</li>
</ul>

<p>&nbsp;</p>

<p><strong>Why this matters:</strong></p>
<ul style="padding-left:20px;">
<li>First AI corruption detection system in the Western Balkans</li>
<li>Built entirely as a private initiative - no government funding</li>
<li>Uses ML pipeline with 150+ features for risk scoring</li>
<li>RAG (Retrieval-Augmented Generation) for intelligent document search</li>
<li>While Albania just created a Ministry for AI, Macedonia already has a working AI tool tackling one of the region's biggest problems</li>
</ul>

<p>&nbsp;</p>

<p><strong>Tech stack:</strong> Next.js, FastAPI, PostgreSQL, Scrapy + Playwright, Gemini AI embeddings, Python ML pipeline</p>

<p>&nbsp;</p>

<p>Would you be interested in covering this? We can provide:</p>
<ul style="padding-left:20px;">
<li>Live demo of the AI detection system</li>
<li>Technical deep-dive for your audience</li>
<li>Interview with the team</li>
<li>Specific examples of flagged tenders with explanations</li>
</ul>

<p>&nbsp;</p>

<p>Feel free to reply to this email or call +389 70 253 467.</p>

<p>&nbsp;</p>

<p>Best regards,</p>
<p><strong>Tamara Sarsevska</strong><br>NabavkiData<br>hello@nabavkidata.com<br><a href="https://nabavkidata.com" style="color:#1a5276;">nabavkidata.com</a></p>

<hr style="border:none; border-top:1px solid #eee; margin:30px 0;">
<p style="font-size:12px; color:#999;">TAMSAR INC | 131 Continental Dr Ste 305, New Castle, DE 19713</p>
</div></body></html>"""


GOV_SUBJECT = "НабавкиДата - AI систем за анализа на јавни набавки (предлог за соработка)"
GOV_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Georgia, serif; font-size:16px; line-height:1.8; color:#1a1a1a;">
<div style="max-width:640px; margin:0 auto;">

<p>Почитувани,</p>

<p>Ви се обраќам од <strong>НабавкиДата</strong> (<a href="https://nabavkidata.com" style="color:#1a5276;">nabavkidata.com</a>) - платформа која користи вештачка интелигенција за анализа и мониторинг на јавните набавки во Македонија.</p>

<p>&nbsp;</p>

<p><strong>Што претставува системот:</strong></p>

<p>Развивме AI систем кој автоматски анализира податоци од јавните набавки и идентификува потенцијални неправилности. Системот користи <strong>50+ индикатори за ризик</strong>, базирани на меѓународни методологии (Светска Банка, OECD, Dozorro), и ги означува случаите за понатамошна проверка.</p>

<p>&nbsp;</p>

<p><strong>Системот детектира:</strong></p>
<ul style="padding-left:20px;">
<li>Тендери со единствен понудувач</li>
<li>Повторливо доделување на договори на исти компании</li>
<li>Ценовни отстапувања од пазарните вредности</li>
<li>Нереално кратки рокови за поднесување понуди</li>
<li>Поврзаност меѓу понудувачи (ист сопственик, адреса, директор)</li>
<li>Сомнително слични понуди (bid clustering)</li>
</ul>

<p>&nbsp;</p>

<p><strong>Нашата цел</strong> е овој систем да биде <strong>комплементарен</strong> на постоечките институционални механизми - да служи како дополнителна алатка за рано предупредување која помага да се насочат ресурсите за контрола таму каде што се најпотребни.</p>

<p>&nbsp;</p>

<p>Платформата веќе ја користат над <strong>4,500 компании и граѓани</strong>. Би сакале да разговараме за можности за <strong>соработка и интеграција</strong> со вашата институција.</p>

<p>&nbsp;</p>

<p>Можеме да обезбедиме:</p>
<ul style="padding-left:20px;">
<li>Презентација на системот</li>
<li>Демо на AI детекцијата</li>
<li>Конкретни анализи и извештаи</li>
<li>Бесплатен пристап за институционални потреби</li>
</ul>

<p>&nbsp;</p>

<p>Доколку сакате повеќе информации, слободно контактирајте нè на +389 70 253 467 или одговорете на овој мејл.</p>

<p>&nbsp;</p>

<p>Со почит,</p>
<p><strong>Тамара Сарсевска</strong><br>НабавкиДата<br>hello@nabavkidata.com<br><a href="https://nabavkidata.com" style="color:#1a5276;">nabavkidata.com</a></p>

<hr style="border:none; border-top:1px solid #eee; margin:30px 0;">
<p style="font-size:12px; color:#999;">TAMSAR INC | 131 Continental Dr Ste 305, New Castle, DE 19713</p>
</div></body></html>"""


ACADEMIC_SUBJECT = "AI за детекција на корупција во јавни набавки - можност за соработка"
ACADEMIC_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Georgia, serif; font-size:16px; line-height:1.8; color:#1a1a1a;">
<div style="max-width:640px; margin:0 auto;">

<p>Почитуван/а професоре,</p>

<p>Ви се обраќам од <strong>НабавкиДата</strong> (<a href="https://nabavkidata.com" style="color:#1a5276;">nabavkidata.com</a>) - платформа која користи вештачка интелигенција за анализа на јавните набавки и детекција на корупциски обрасци.</p>

<p>&nbsp;</p>

<p><strong>Нашиот систем:</strong></p>
<ul style="padding-left:20px;">
<li>Анализира <strong>15,000+ тендери</strong> со <strong>50+ индикатори за ризик</strong></li>
<li>Користи ML pipeline со 150+ карактеристики за проценка на ризик</li>
<li>Базиран на методологии на Светска Банка, OECD и украинскиот Dozorro</li>
<li>Семантичко пребарување со Gemini embeddings и RAG архитектура</li>
<li>Веќе го користат 4,500+ корисници</li>
</ul>

<p>&nbsp;</p>

<p><strong>Предлог за соработка:</strong></p>

<p>Верувам дека нашата платформа и податоци можат да бидат корисни за академски истражувања. Би сакале да понудиме:</p>

<ul style="padding-left:20px;">
<li><strong>Бесплатен пристап</strong> до платформата за истражувачки цели</li>
<li><strong>Пристап до анонимизирани податоци</strong> за анализа на обрасци во јавните набавки</li>
<li><strong>Можност за заеднички истражувачки проект</strong> или студија на случај</li>
<li><strong>Гостинско предавање</strong> за студенти за примена на AI во борбата против корупцијата</li>
</ul>

<p>&nbsp;</p>

<p>Доколку сте заинтересирани, со задоволство ќе организираме средба или презентација.</p>

<p>Контакт: +389 70 253 467 или одговорете на овој мејл.</p>

<p>&nbsp;</p>

<p>Со почит,</p>
<p><strong>Тамара Сарсевска</strong><br>НабавкиДата<br>hello@nabavkidata.com<br><a href="https://nabavkidata.com" style="color:#1a5276;">nabavkidata.com</a></p>

<hr style="border:none; border-top:1px solid #eee; margin:30px 0;">
<p style="font-size:12px; color:#999;">TAMSAR INC | 131 Continental Dr Ste 305, New Castle, DE 19713</p>
</div></body></html>"""


INTL_SUBJECT = "NabavkiData - AI Corruption Detection for Public Procurement (North Macedonia)"
INTL_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Georgia, serif; font-size:16px; line-height:1.8; color:#1a1a1a;">
<div style="max-width:640px; margin:0 auto;">

<p>Hello,</p>

<p>I'm writing from <strong>NabavkiData</strong> (<a href="https://nabavkidata.com" style="color:#1a5276;">nabavkidata.com</a>) - a civic tech platform from North Macedonia that uses AI to detect corruption patterns in public procurement.</p>

<p>&nbsp;</p>

<p><strong>What we do:</strong></p>
<ul style="padding-left:20px;">
<li>AI system analyzing <strong>15,000+ public tenders</strong> with <strong>50+ risk indicators</strong></li>
<li>Built on World Bank, OECD, and Dozorro (Ukraine) methodologies</li>
<li>Detects: single-bidder tenders, repeat winners, price anomalies, bid clustering, connected companies, specification rigging, short deadlines</li>
<li>ML pipeline with 150+ features for automated risk scoring</li>
<li>Already used by <strong>4,500+ users</strong> (companies, citizens, researchers)</li>
</ul>

<p>&nbsp;</p>

<p><strong>Context:</strong></p>
<p>North Macedonia spends hundreds of millions annually on public procurement, yet lacks automated monitoring tools. While the country pursues EU accession, procurement transparency remains a critical challenge. Our platform fills this gap as a <strong>civil society initiative</strong> - built without government funding.</p>

<p>&nbsp;</p>

<p><strong>We'd love to:</strong></p>
<ul style="padding-left:20px;">
<li>Be featured on your platform / in your directory</li>
<li>Explore partnership or collaboration opportunities</li>
<li>Share our methodology and findings</li>
<li>Provide a demo or detailed technical overview</li>
</ul>

<p>&nbsp;</p>

<p>Feel free to reach out at +389 70 253 467 or reply to this email.</p>

<p>&nbsp;</p>

<p>Best regards,</p>
<p><strong>Tamara Sarsevska</strong><br>NabavkiData<br>hello@nabavkidata.com<br><a href="https://nabavkidata.com" style="color:#1a5276;">nabavkidata.com</a></p>

<hr style="border:none; border-top:1px solid #eee; margin:30px 0;">
<p style="font-size:12px; color:#999;">TAMSAR INC | 131 Continental Dr Ste 305, New Castle, DE 19713</p>
</div></body></html>"""


# ============================================================
# ALL CONTACTS
# ============================================================

CONTACTS = [
    # --- MK Tech/Startup Blogs (Macedonian) ---
    ("IT.mk", "redakcija@it.mk", TECH_BLOG_SUBJECT, TECH_BLOG_HTML, "tech"),
    ("Startup Macedonia", "startupmacedonia@gmail.com", TECH_BLOG_SUBJECT, TECH_BLOG_HTML, "tech"),
    ("Startup Macedonia (platform)", "startupmacedonia.platform@gmail.com", TECH_BLOG_SUBJECT, TECH_BLOG_HTML, "tech"),
    ("Kajgana Forum", "contact@kajgana.com", TECH_BLOG_SUBJECT, TECH_BLOG_HTML, "tech"),
    ("MKhost Blog", "info@mkhost.com.mk", TECH_BLOG_SUBJECT, TECH_BLOG_HTML, "tech"),
    ("Macedonia2025", "office@macedonia2025.com", TECH_BLOG_SUBJECT, TECH_BLOG_HTML, "tech"),
    ("FITD", "info@fitr.mk", TECH_BLOG_SUBJECT, TECH_BLOG_HTML, "tech"),

    # --- Balkan/International Tech Blogs (English) ---
    ("Netokracija", "info@netokracija.com", TECH_BLOG_EN_SUBJECT, TECH_BLOG_EN_HTML, "tech-en"),
    ("The Recursive", "tips@therecursive.com", TECH_BLOG_EN_SUBJECT, TECH_BLOG_EN_HTML, "tech-en"),
    ("Startit.rs", "redakcija@startit.rs", TECH_BLOG_EN_SUBJECT, TECH_BLOG_EN_HTML, "tech-en"),
    ("EU-Startups", "olga@eu-startups.com", TECH_BLOG_EN_SUBJECT, TECH_BLOG_EN_HTML, "tech-en"),
    ("Emerging Europe", "office@reinvantage.org", TECH_BLOG_EN_SUBJECT, TECH_BLOG_EN_HTML, "tech-en"),
    ("SEEbiz.eu", "info@seebiz.eu", TECH_BLOG_EN_SUBJECT, TECH_BLOG_EN_HTML, "tech-en"),
    ("GovInsider", "editorial@govinsider.asia", TECH_BLOG_EN_SUBJECT, TECH_BLOG_EN_HTML, "tech-en"),

    # --- Government Bodies (Macedonian) ---
    ("Биро за јавни набавки", "info@bjn.gov.mk", GOV_SUBJECT, GOV_HTML, "gov"),
    ("Државен завод за ревизија", "dzr@dzr.mk", GOV_SUBJECT, GOV_HTML, "gov"),
    ("Народен правобранител", "contact@ombudsman.mk", GOV_SUBJECT, GOV_HTML, "gov"),

    # --- EU Delegation (English) ---
    ("EU Delegation to North Macedonia", "delegation-north-macedonia@eeas.europa.eu", INTL_SUBJECT, INTL_HTML, "intl"),

    # --- Academic (Macedonian) ---
    ("Prof. Gjorgji Madjarov (FINKI)", "gjorgji.madjarov@finki.ukim.mk", ACADEMIC_SUBJECT, ACADEMIC_HTML, "academic"),
    ("Prof. Dimitar Trajanov (FINKI)", "dimitar.trajanov@finki.ukim.mk", ACADEMIC_SUBJECT, ACADEMIC_HTML, "academic"),
    ("Правен факултет УКИМ", "praven@pf.ukim.edu.mk", ACADEMIC_SUBJECT, ACADEMIC_HTML, "academic"),

    # --- Anti-corruption / Think tanks (Macedonian) ---
    ("Транспаренси МК - Филип Пашу", "filip.pashu@transparency-mk.org.mk", GOV_SUBJECT, GOV_HTML, "ngo"),
    ("ИДСЦС - Миша Поповиќ", "misha@idscs.org.mk", GOV_SUBJECT, GOV_HTML, "ngo"),

    # --- International platforms (English) ---
    ("Open Contracting Partnership", "data@open-contracting.org", INTL_SUBJECT, INTL_HTML, "intl"),
    ("U4 Anti-Corruption Centre", "helpdesk@u4.no", INTL_SUBJECT, INTL_HTML, "intl"),
]


def send_email(client, name, email, subject, html_body):
    r = client.post(
        "https://api.postmarkapp.com/email",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": POSTMARK_API_TOKEN
        },
        json={
            "From": f"{FROM_NAME} <{FROM_EMAIL}>",
            "ReplyTo": FROM_EMAIL,
            "To": email,
            "Subject": subject,
            "HtmlBody": html_body,
            "TextBody": "See HTML version",
            "MessageStream": "outbound",
            "TrackOpens": True,
            "TrackLinks": "HtmlAndText"
        }
    )
    if r.status_code == 200:
        mid = r.json().get("MessageID", "")[:16]
        return True, mid
    else:
        return False, r.text[:100]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()

    is_live = args.live and not args.dry_run

    logger.info("=" * 60)
    logger.info("PR OUTREACH - All Channels")
    logger.info(f"Mode: {'LIVE' if is_live else 'DRY RUN'}")
    logger.info(f"Contacts: {len(CONTACTS)}")
    logger.info("=" * 60)

    if not is_live:
        for name, email, subject, _, category in CONTACTS:
            logger.info(f"  [{category}] {name} <{email}>")
            logger.info(f"    Subject: {subject[:60]}...")
        logger.info(f"\nUse --live to send")
        return

    sent = 0
    errors = 0

    client = httpx.Client(timeout=30)

    for name, email, subject, html, category in CONTACTS:
        logger.info(f"  [{category}] {name} <{email}>")
        success, msg = send_email(client, name, email, subject, html)

        if success:
            sent += 1
            logger.info(f"    -> Sent ({msg})")
        else:
            errors += 1
            logger.error(f"    -> ERROR: {msg}")

        time.sleep(2)

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"COMPLETE - Sent: {sent}, Errors: {errors}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
