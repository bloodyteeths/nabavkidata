#!/usr/bin/env python3
"""
PR Pitch Wave 3 - Send to individual journalists found via Apollo
Focus: Relevant MK media journalists, editors, correspondents
"""
import os
import asyncio
import logging
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

POSTMARK_API_TOKEN = os.getenv('POSTMARK_API_TOKEN', '33d10a6c-0906-42c6-ab14-441ad12b9e2a')
POSTMARK_FROM_EMAIL = 'hello@nabavkidata.com'
POSTMARK_FROM_NAME = 'Тамара Сарсевска'

# Curated list of relevant journalists from Apollo search
# Filtered: only actual journalists/editors at MK media outlets
# Excluded: video editors, freelancers on Fiverr/Upwork, non-media orgs
JOURNALIST_CONTACTS = [
    # === Telma TV ===
    {"name": "Ognen Cancarevik", "email": "ognen@telma.com.mk", "title": "Investigative Host"},
    {"name": "Marija Mitevska", "email": "marija@telma.com.mk", "title": "Journalist"},
    {"name": "Mirjana Joveska", "email": "mirjana@telma.com.mk", "title": "Journalist"},
    {"name": "Tamara Grncaroska", "email": "tamara@telma.com.mk", "title": "Journalist"},
    {"name": "Petar Dogov", "email": "petar@telma.com.mk", "title": "Journalist"},
    {"name": "Goran Petreski", "email": "goran@telma.com.mk", "title": "Editor"},
    {"name": "Bobi Hristov", "email": "bobi@telma.com.mk", "title": "Editor"},
    {"name": "Emilija Lazarevska", "email": "emilija@telma.com.mk", "title": "Editor"},
    {"name": "Violeta Zajkova", "email": "violeta@telma.com.mk", "title": "Journalist"},
    {"name": "Marko Mark", "email": "marko@telma.com.mk", "title": "TV Host & Editor"},
    {"name": "Tea Dimkovska", "email": "tea@telma.com.mk", "title": "Podcast Host"},
    {"name": "Cece Trajkovska", "email": "cece@telma.com.mk", "title": "Morning Show Host"},
    {"name": "Branko Kazakovski", "email": "branko@telma.com.mk", "title": "Sports Journalist"},

    # === Radio Free Europe / Radio Liberty ===
    {"name": "Vladimir Kalinski", "email": "kalinskiv@rferl.org", "title": "Journalist"},
    {"name": "Vanja Micevska", "email": "micevskav@rferl.org", "title": "Journalist"},
    {"name": "Mihailo Donev", "email": "donevm@rferl.org", "title": "Journalist"},
    {"name": "Srgjan Stojancov", "email": "stojancovs@rferl.org", "title": "Journalist"},
    {"name": "Zorana Spasovska", "email": "spasovskaz@rferl.org", "title": "Investigative Journalist"},

    # === MRT (Macedonian Radio Television) ===
    {"name": "Mirjana Pistolova", "email": "mirjanap@mrtsos.com", "title": "Reporter"},
    {"name": "Karolina Petkovska", "email": "karolina.petkovska@mrt.com.mk", "title": "Journalist"},
    {"name": "Kaltrina Mustafa", "email": "kaltrina.mustafa@mrt.com.mk", "title": "Journalist"},
    {"name": "Rade Spasovski", "email": "rade.spasovski@mrt.com.mk", "title": "Journalist"},
    {"name": "Martin Pushevski", "email": "martin.pushevski@mrt.com.mk", "title": "TV Reporter & Editor"},
    {"name": "Anita Velkovska", "email": "anita.velkovska@mrt.com.mk", "title": "Journalist"},
    {"name": "Martin Nikolovski", "email": "martin.nikolovski@mrt.com.mk", "title": "Journalist"},
    {"name": "Maja Stojanova", "email": "maja.stojanova@mrt.com.mk", "title": "Journalist"},

    # === BIRN / Investigative ===
    {"name": "Vasko Magleshov", "email": "vasko.magleshov@birn.eu.com", "title": "Journalist, BIRN"},
    {"name": "Prizma BIRN", "email": "prizma@birn.eu.com", "title": "Journalist, BIRN"},

    # === 360 Stepeni ===
    {"name": "Aleksandar Dimitrievski", "email": "aleksandar.dimitrievski@360stepeni.mk", "title": "Journalist"},

    # === Metamorphosis Foundation ===
    {"name": "Antonija Popovska", "email": "antonija@metamorphosis.org.mk", "title": "Journalist"},
    {"name": "Dance Bajdevska", "email": "dance@metamorphosis.org.mk", "title": "Program Director"},

    # === Makfax ===
    {"name": "Nenad Cvetanov", "email": "nenad.cvetanov@makfax.com.mk", "title": "Journalist"},
    {"name": "Vesna Drvosanski", "email": "vesna.drvosanski@makfax.com.mk", "title": "Journalist"},

    # === Faktor.mk ===
    {"name": "Aleksandar Todeski", "email": "aleksandar.t@faktor.mk", "title": "Journalist"},
    {"name": "Daniela Trajkovska", "email": "daniela.t@faktor.mk", "title": "Journalist"},

    # === Kapital Media Group ===
    {"name": "Dejan Azeski", "email": "dejan.azeski@kapital.mk", "title": "Journalist"},
    {"name": "Vladimir Gocevski", "email": "vladimir.gocevski@kapital.mk", "title": "Journalist"},
    {"name": "Verica Jordanova", "email": "verica.jordanova@kapital.mk", "title": "Editor"},

    # === Sloboden Pecat ===
    # (already sent to org email, adding individual)

    # === Bloomberg Adria ===
    {"name": "Natasa Stefanova", "email": "natasa.hadzispirkoska.stefanova@bloombergadria.com", "title": "Journalist"},
    {"name": "Irena Stefanovska", "email": "irena.stefanovska@bloombergadria.com", "title": "Producer/Presenter"},

    # === Al Jazeera Balkans ===
    {"name": "Milka Smilevska", "email": "milka.smilevska@aljazeera.net", "title": "Journalist"},

    # === Other notable journalists ===
    {"name": "Kole Casule", "email": "kole.casule@reuters.com", "title": "Reuters Correspondent"},
    {"name": "Andrijana Jovanovska", "email": "andrijana@crnobelo.com", "title": "Journalist, CRNOBELO"},
    {"name": "Angela Ivanoska", "email": "angela_ivanoska@radiomof.mk", "title": "Radio MOF Journalist"},
    {"name": "Furkan Saliu", "email": "furkan@tv21.tv", "title": "Journalist, TV21"},
    {"name": "Vesna Sherovska", "email": "vesna@tera.mk", "title": "Journalist, Tera TV"},
]

SUBJECT = "AI алатка на македонска компанија открива сомнителни тендери - можност за приказна"

HTML_BODY_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Georgia, 'Times New Roman', serif; font-size:16px; line-height:1.8; color:#1a1a1a; background-color:#ffffff;">
<div style="max-width:640px; margin:0 auto;">

<p>Почитуван/а {name},</p>

<p>Ви пишувам со предлог за приказна која верувам дека ќе биде интересна за вас и за вашата публика.</p>

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

TEXT_BODY_TEMPLATE = """Почитуван/а {name},

Ви пишувам со предлог за приказна која верувам дека ќе биде интересна за вас и за вашата публика.

НАКРАТКО: Македонска компанија изгради AI систем кој автоматски анализира јавни набавки и открива шеми на сомнително однесување - наместени тендери, ценовни аномалии, повторливи победници и нетранспарентни постапки.

---

ЗОШТО Е ОВА ВАЖНО ЗА МАКЕДОНИЈА

Македонија од години се бори со корупцијата во јавните набавки. Секоја влада вети реформи, но проблемот останува. Причината е едноставна: нема систем кој автоматски ги следи податоците. Стотици тендери се објавуваат секој месец - невозможно е рачно да се анализираат сите.

Нашиот AI систем го прави токму тоа. Автоматски, без човечка пристрасност, без политички притисок.

ШТО ОТКРИВА СИСТЕМОТ

Анализиравме над 15,000 тендери со 50+ индикатори за ризик, базирани на методологијата на Светска Банка, OECD и украинскиот Dozorro систем:

- Тендери со само еден понудувач
- Повторливи победници
- Ценовни аномалии
- Кратки рокови
- Групирани понуди
- Поврзани компании
- Доцни измени

---

ШТО НУДИМЕ

- Интервју со основачот
- Демонстрација на AI системот во живо
- Конкретни примери на означени тендери со објаснување
- Бесплатен пристап до платформата за истражувачки цели

Доколку сакате повеќе информации или да закажеме разговор, слободно одговорете на овој мејл или јавете се на +389 70 253 467.

Со почит,
Тамара Сарсевска
НабавкиДата
hello@nabavkidata.com
nabavkidata.com
"""


async def send_email(client, contact):
    first_name = contact["name"].split()[0]
    html = HTML_BODY_TEMPLATE.format(name=first_name)
    text = TEXT_BODY_TEMPLATE.format(name=first_name)

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
            "To": contact["email"],
            "Subject": SUBJECT,
            "HtmlBody": html,
            "TextBody": text,
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
    logger.info("PR PITCH Wave 3 - Individual Journalists")
    logger.info(f"Mode: {'LIVE' if is_live else 'DRY RUN'}")
    logger.info(f"Contacts: {len(JOURNALIST_CONTACTS)}")
    logger.info("=" * 60)

    if not is_live:
        for c in JOURNALIST_CONTACTS:
            logger.info(f"  {c['name']} ({c['title']}) <{c['email']}>")
        logger.info(f"\nTo send for real: --live")
        return

    sent = 0
    errors = 0

    async with httpx.AsyncClient() as client:
        for c in JOURNALIST_CONTACTS:
            logger.info(f"  {c['name']} ({c['title']}) <{c['email']}>")
            result = await send_email(client, c)

            if result['success']:
                sent += 1
                mid = result['message_id'][:16]
                logger.info(f"    -> Sent ({mid}...)")
            else:
                errors += 1
                logger.error(f"    -> ERROR: {result['error'][:80]}")

            await asyncio.sleep(2.0)

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"COMPLETE - Sent: {sent}, Errors: {errors}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
