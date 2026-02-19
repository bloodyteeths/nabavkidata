#!/usr/bin/env python3
"""Send PR pitch to TRT Balkans contacts"""
import httpx
import time

POSTMARK_API_TOKEN = "33d10a6c-0906-42c6-ab14-441ad12b9e2a"

TRT_CONTACTS = [
    ("Hamza Ejupi", "hamza.ejupi@trt.net.tr", "Marketing Specialist"),
    ("Faruk Aliji", "faruk.aliji@trt.net.tr", "Social Media Manager"),
    ("Melani Risteska", "melani.risteska@trt.net.tr", "Producer/Presenter"),
    ("Tahsin Colak", "tahsin.colak@trt.net.tr", "Correspondent"),
    ("Marjan Stoilov", "mstoilov@trt.com", "TRT"),
]

SUBJECT = "AI алатка на македонска компанија открива сомнителни тендери - можност за приказна"

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Georgia, serif; font-size:16px; line-height:1.8; color:#1a1a1a; background-color:#ffffff;">
<div style="max-width:640px; margin:0 auto;">

<p>Почитуван/а $$FIRST$$,</p>

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

sent = 0
errors = 0
client = httpx.Client(timeout=30)

for full_name, email, title in TRT_CONTACTS:
    first = full_name.split()[0]
    html = HTML_TEMPLATE.replace("$$FIRST$$", first)

    print(f"  {full_name} ({title}) <{email}>...", end=" ", flush=True)
    r = client.post(
        "https://api.postmarkapp.com/email",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": POSTMARK_API_TOKEN
        },
        json={
            "From": "Тамара Сарсевска <hello@nabavkidata.com>",
            "ReplyTo": "hello@nabavkidata.com",
            "To": email,
            "Subject": SUBJECT,
            "HtmlBody": html,
            "TextBody": "See HTML version",
            "MessageStream": "outbound",
            "TrackOpens": True,
            "TrackLinks": "HtmlAndText"
        }
    )
    if r.status_code == 200:
        mid = r.json().get("MessageID", "")[:16]
        print(f"Sent ({mid})")
        sent += 1
    else:
        print(f"ERROR: {r.text[:80]}")
        errors += 1
    time.sleep(2)

print(f"\nCOMPLETE - Sent: {sent}, Errors: {errors}")
