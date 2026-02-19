#!/usr/bin/env python3
"""
PR Pitch - Send to all Macedonian media outlets
Focus: AI corruption detection in public procurement
"""
import os
import sys
import asyncio
import logging
from datetime import datetime
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

POSTMARK_API_TOKEN = os.getenv('POSTMARK_API_TOKEN', '33d10a6c-0906-42c6-ab14-441ad12b9e2a')
POSTMARK_FROM_EMAIL = 'hello@nabavkidata.com'
POSTMARK_FROM_NAME = 'Тамара Сарсевска'

# Wave 2 - New contacts + alternative emails for bounced ones
# (Wave 1 already sent to: 24 Vesti, Alsat-M, SCOOP, Prizma, IRL, A1on, Fokus,
#  Republika, Meta.mk, MASIT, Stopanska Komora, Radio MOF)
MEDIA_CONTACTS = [
    # === RETRY: Alternative emails for Wave 1 bounces ===
    {"name": "Телма ТВ", "email": "telma@telma.com.mk", "type": "tv"},
    {"name": "Сител ТВ", "email": "vesti@sitel.com.mk", "type": "tv"},
    {"name": "Канал 5", "email": "desk@kanal5.com.mk", "type": "tv"},
    {"name": "СДК.мк", "email": "info@sdk.mk", "type": "portal"},
    {"name": "Нова ТВ", "email": "redakcija@novatv.mk", "type": "tv"},

    # === NEW: News Portals ===
    {"name": "Слободен Печат", "email": "webredakcija@pecat.mk", "type": "portal"},
    {"name": "Макфакс", "email": "administracija@makfax.com.mk", "type": "portal"},
    {"name": "Независен Весник", "email": "redakcija@nezavisen.mk", "type": "portal"},
    {"name": "Фактор.мк", "email": "contact@faktor.mk", "type": "business"},
    {"name": "Локално.мк", "email": "glavenured@lokalno.mk", "type": "portal"},
    {"name": "Press24.mk", "email": "contact@press24.mk", "type": "portal"},
    {"name": "Вечер.press", "email": "vecer@vecer.press", "type": "portal"},
    {"name": "НетПрес", "email": "netpress@netpress.com.mk", "type": "portal"},
    {"name": "Курир.мк", "email": "redakcija@kurir.mk", "type": "portal"},
    {"name": "МКД.мк", "email": "kontakt@mkd.mk", "type": "portal"},
    {"name": "Нова Македонија", "email": "nm@novamakedonija.com.mk", "type": "portal"},
    {"name": "МИА", "email": "mia@mia.mk", "type": "portal"},
    {"name": "Порталб.мк", "email": "info@portalb.mk", "type": "portal"},
    {"name": "Радио Лидер", "email": "mail@lider.mk", "type": "radio"},

    # === NEW: International Media ===
    {"name": "Радио Слободна Европа", "email": "slobodnaevropamk@rferl.org", "type": "international"},

    # === NEW: Investigative / Fact-checking ===
    {"name": "OCCRP", "email": "press@occrp.org", "type": "investigative"},
    {"name": "БИРН (Balkan Insight)", "email": "editor@birn.eu.com", "type": "investigative"},
    {"name": "Вистиномер (Метаморфозис)", "email": "info@metamorphosis.org.mk", "type": "investigative"},

    # === NEW: Anti-corruption NGOs ===
    {"name": "Транспаренси Интернешнл МК", "email": "info@transparency.mk", "type": "ngo"},
    {"name": "Центар за граѓански комуникации", "email": "center@ccc.org.mk", "type": "ngo"},
    {"name": "ИДСЦС", "email": "contact@idscs.org.mk", "type": "ngo"},
    {"name": "МЦМС", "email": "mcms@mcms.org.mk", "type": "ngo"},
    {"name": "Хелсиншки комитет МК", "email": "helkom@mhc.org.mk", "type": "ngo"},
    {"name": "Аналитика", "email": "info@analyticamk.org", "type": "ngo"},
    {"name": "Реактор", "email": "info@reactor.org.mk", "type": "ngo"},
    {"name": "МИМ", "email": "mim@mim.org.mk", "type": "ngo"},
    {"name": "ДКСК", "email": "contact@dksk.org.mk", "type": "ngo"},
]

SUBJECT = "AI алатка на македонска компанија открива сомнителни тендери - можност за приказна"

HTML_BODY = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Georgia, 'Times New Roman', serif; font-size:16px; line-height:1.8; color:#1a1a1a; background-color:#ffffff;">
<div style="max-width:640px; margin:0 auto;">

<p>Почитувана редакцијо,</p>

<p>Ви пишувам со предлог за приказна која верувам дека ќе биде интересна за вашата публика.</p>

<p>&nbsp;</p>

<p style="font-size:18px;"><strong>Накратко:</strong> Македонска компанија изгради AI систем кој автоматски анализира јавни набавки и открива шеми на сомнително однесување - наместени тендери, ценовни аномалии, повторливи победници и нетранспарентни постапки.</p>

<p>&nbsp;</p>

<hr style="border:none; border-top:1px solid #cccccc; margin:25px 0;">

<p>&nbsp;</p>

<p><strong>ЗОШТО Е ОВА ВАЖНО ЗА МАКЕДОНИЈА</strong></p>

<p>Македонија од години се бори со корупцијата во јавните набавки. Секоја влада вети реформи, но проблемот останува. Причината е едноставна: <strong>нема систем кој автоматски ги следи податоците</strong>. Стотици тендери се објавуваат секој месец - невозможно е рачно да се анализираат сите.</p>

<p>Нашиот AI систем го прави токму тоа. Автоматски, без човечка пристрасност, без политички притисок.</p>

<p>&nbsp;</p>

<p><strong>ШТО ОТКРИВА СИСТЕМОТ</strong></p>

<p>Анализиравме <strong>над 15,000 тендери</strong> со <strong>50+ индикатори за ризик</strong>, базирани на методологијата на Светска Банка, OECD и украинскиот Dozorro систем:</p>

<ul style="padding-left:20px;">
<li><strong>Тендери со само еден понудувач</strong> - кога спецификациите се напишани за точно една фирма</li>
<li><strong>Повторливи победници</strong> - иста фирма постојано добива кај иста институција</li>
<li><strong>Ценовни аномалии</strong> - цени кои значително отстапуваат од пазарните</li>
<li><strong>Кратки рокови</strong> - тендери објавени со помалку од 3 дена за поднесување понуда</li>
<li><strong>Групирани понуди</strong> - сомнително слични цени меѓу различни понудувачи</li>
<li><strong>Поврзани компании</strong> - понудувачи со ист сопственик, адреса или директор</li>
<li><strong>Доцни измени</strong> - промена на спецификации непосредно пред крајниот рок</li>
</ul>

<p>&nbsp;</p>

<p><strong>ЗОШТО Е ОВА РАЗЛИЧНО</strong></p>

<p>Ова не е уште една апликација за следење тендери. Ова е <strong>систем за рано предупредување</strong> - алатка која може да им помогне на институциите, на антикорупциските тела и на јавноста да знаат каде да гледаат.</p>

<p>Наместо да се чека некој да пријави корупција - системот <strong>проактивно ги идентификува сомнителните случаи</strong> и ги означува за понатамошна анализа.</p>

<p>Замислете го ова како <strong>рентген за јавните набавки</strong> - не обвинува никого, но покажува каде треба да се погледне подлабоко.</p>

<p>&nbsp;</p>

<p><strong>КОНТЕКСТ</strong></p>

<p>Додека Албанија неодамна формираше Министерство за AI (прво во регионот), во Македонија - <strong>без државна поддршка</strong> - приватна компанија веќе применува AI за решавање на еден од најголемите проблеми: транспарентноста во трошењето јавни пари.</p>

<p>Системот е достапен на <strong><a href="https://nabavkidata.com" style="color:#1a5276;">nabavkidata.com</a></strong> и веќе го користат над 4,500 компании и граѓани.</p>

<p>&nbsp;</p>

<hr style="border:none; border-top:1px solid #cccccc; margin:25px 0;">

<p>&nbsp;</p>

<p><strong>ШТО НУДИМЕ</strong></p>

<ul style="padding-left:20px;">
<li>Интервју со основачот</li>
<li>Демонстрација на AI системот во живо</li>
<li>Конкретни примери на означени тендери со објаснување</li>
<li>Бесплатен пристап до платформата за истражувачки цели</li>
</ul>

<p>&nbsp;</p>

<p>Доколку сакате повеќе информации или да закажеме разговор, слободно одговорете на овој мејл или јавете се на +389 70 253 467.</p>

<p>&nbsp;</p>

<p>Со почит,</p>
<p><strong>Тамара Сарсевска</strong><br>
НабавкиДата<br>
hello@nabavkidata.com<br>
<a href="https://nabavkidata.com" style="color:#1a5276;">nabavkidata.com</a></p>

<p>&nbsp;</p>

<hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">

<p style="font-size:12px; color:#999999;">
TAMSAR INC | 131 Continental Dr Ste 305, New Castle, DE 19713
</p>

</div>
</body>
</html>"""

TEXT_BODY = """Почитувана редакцијо,

Ви пишувам со предлог за приказна која верувам дека ќе биде интересна за вашата публика.

НАКРАТКО: Македонска компанија изгради AI систем кој автоматски анализира јавни набавки и открива шеми на сомнително однесување - наместени тендери, ценовни аномалии, повторливи победници и нетранспарентни постапки.

---

ЗОШТО Е ОВА ВАЖНО ЗА МАКЕДОНИЈА

Македонија од години се бори со корупцијата во јавните набавки. Секоја влада вети реформи, но проблемот останува. Причината е едноставна: нема систем кој автоматски ги следи податоците. Стотици тендери се објавуваат секој месец - невозможно е рачно да се анализираат сите.

Нашиот AI систем го прави токму тоа. Автоматски, без човечка пристрасност, без политички притисок.

ШТО ОТКРИВА СИСТЕМОТ

Анализиравме над 15,000 тендери со 50+ индикатори за ризик, базирани на методологијата на Светска Банка, OECD и украинскиот Dozorro систем:

- Тендери со само еден понудувач - кога спецификациите се напишани за точно една фирма
- Повторливи победници - иста фирма постојано добива кај иста институција
- Ценовни аномалии - цени кои значително отстапуваат од пазарните
- Кратки рокови - тендери објавени со помалку од 3 дена за поднесување понуда
- Групирани понуди - сомнително слични цени меѓу различни понудувачи
- Поврзани компании - понудувачи со ист сопственик, адреса или директор
- Доцни измени - промена на спецификации непосредно пред крајниот рок

ЗОШТО Е ОВА РАЗЛИЧНО

Ова не е уште една апликација за следење тендери. Ова е систем за рано предупредување - алатка која може да им помогне на институциите, на антикорупциските тела и на јавноста да знаат каде да гледаат.

Наместо да се чека некој да пријави корупција - системот проактивно ги идентификува сомнителните случаи и ги означува за понатамошна анализа.

Замислете го ова како рентген за јавните набавки - не обвинува никого, но покажува каде треба да се погледне подлабоко.

КОНТЕКСТ

Додека Албанија неодамна формираше Министерство за AI (прво во регионот), во Македонија - без државна поддршка - приватна компанија веќе применува AI за решавање на еден од најголемите проблеми: транспарентноста во трошењето јавни пари.

Системот е достапен на nabavkidata.com и веќе го користат над 4,500 компании и граѓани.

---

ШТО НУДИМЕ

- Интервју со основачот
- Демонстрација на AI системот во живо
- Конкретни примери на означени тендери со објаснување
- Бесплатен пристап до платформата за истражувачки цели

Доколку сакате повеќе информации или да закажеме разговор, слободно одговорете на овој мејл.

Со почит,
Тамара Сарсевска
НабавкиДата
hello@nabavkidata.com
nabavkidata.com
"""


async def send_email(client: httpx.AsyncClient, to_email: str, to_name: str) -> dict:
    """Send PR pitch via Postmark"""
    response = await client.post(
        "https://api.postmarkapp.com/email",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": POSTMARK_API_TOKEN
        },
        json={
            "From": f"{POSTMARK_FROM_NAME} <{POSTMARK_FROM_EMAIL}>",
            "ReplyTo": POSTMARK_FROM_EMAIL,
            "To": to_email,
            "Subject": SUBJECT,
            "HtmlBody": HTML_BODY,
            "TextBody": TEXT_BODY,
            "MessageStream": "outbound",
            "TrackOpens": True,
            "TrackLinks": "HtmlAndText"
        },
        timeout=30.0
    )

    if response.status_code == 200:
        return {"success": True, "message_id": response.json().get("MessageID")}
    else:
        return {"success": False, "error": response.text}


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()

    is_live = args.live and not args.dry_run

    logger.info("=" * 60)
    logger.info("PR PITCH - Macedonian Media Outreach")
    logger.info(f"Mode: {'LIVE' if is_live else 'DRY RUN'}")
    logger.info(f"Contacts: {len(MEDIA_CONTACTS)}")
    logger.info("=" * 60)

    if not is_live:
        logger.info("DRY RUN - Would send to:")
        for c in MEDIA_CONTACTS:
            logger.info(f"  [{c['type']}] {c['name']} <{c['email']}>")
        logger.info(f"\nSubject: {SUBJECT}")
        logger.info("\nTo send for real, use: --live")
        return

    sent = 0
    errors = 0

    async with httpx.AsyncClient() as client:
        for c in MEDIA_CONTACTS:
            logger.info(f"[{c['type']}] {c['name']} <{c['email']}>")
            result = await send_email(client, c['email'], c['name'])

            if result['success']:
                sent += 1
                logger.info(f"  ✓ Sent ({result['message_id'][:20]}...)")
            else:
                errors += 1
                logger.error(f"  ✗ Error: {result['error'][:80]}")

            await asyncio.sleep(2.0)

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"COMPLETE - Sent: {sent}, Errors: {errors}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
