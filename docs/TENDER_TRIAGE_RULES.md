# Tender triage — screening rules

Applied at triage, **before** any deep analysis or subagent fan-out.
Approved by Atilla 19.10.2026 after a nine-tender scan produced zero biddable lots.

Bidder context: Фактурино ДООЕЛ Велес, founded 06.02.2026, two people, not VAT-registered,
six BELCERT ISO certificates. No company references predating Feb 2026 — that is the standing
killer and most walls reduce to it.

## 1. Maintenance value floor — ~400.000 МКД

Auto-walk maintenance tenders whose **expected award** is below roughly 400.000 МКД,
**unless we already hold a contract with that buyer**, in which case the desk is already staffed
for them and the threshold drops.

The cost of a maintenance contract is the standing SLA obligation, not the ticket volume. A
two-hour critical SLA costs the same to hold open whether it pays 200.000 or 900.000. Our ДТИР
cost floor is ~200.000/year, so a 200.000 contract is break-even to loss-making.

**Expected award is not the estimated value.** Derive it from the buyer's own prior awards for
comparable systems. Example: Министерство за енергетика publishes no estimate, but its awarded
software-maintenance contracts cluster at 114.000–354.000 (ФОКСИТ, ЕДУСОФТ, СМАРТ ТЕЧ) — so the
build cost of 1.575.000 was the wrong anchor and the lot was below floor.

## 2. „Не го поседува изворниот код" = NO-GO

Any statement that the buyer does not hold the source code, or offers only supervised „увид"
under an изјава за доверливост, is an automatic walk — especially where the scope still obliges
the winner to fix bugs or correct modules. You cannot maintain code you are not given.

Grep the specification for:
`не го поседува изворниот код` · `изработен од надворешен добавувач` · `увид во апликативниот
софтвер` · `изјава за доверливост`

Confirmed on 17400 МЕР, 16251 ДЗР, 13252 Виница, 16146 РБСМ. The contrast case is ДТИР, where
Чл. 13 vests the code in the buyer and they delivered it — that is what makes maintenance
deliverable.

## 3. Read the технички спецификации before any GO

Never issue a GO verdict from the тендерска документација alone. The walls live in the
specification as often as in the ТД.

If the portal refuses the attachment, check our own extraction first — it is usually already
there:

```sql
SELECT d.file_name, length(d.content_text)
FROM documents d
JOIN tenders t ON (d.tender_id = t.tender_id OR d.tender_id = t.tender_uuid::text)
WHERE t.tender_id = 'NNNNN/2026';
```

Incident that produced this rule: 17400/2026 was called a conditional GO from the ТД PDF after
the specification .docx returned HTTP 409 from ЕСЈН. The extracted text was in `documents` the
whole time and contained the source-code clause that killed the tender.

## Order

Rule 1 (value) → Rule 2 (grep) → Rule 3 (read) → deep analysis.
The first two are cheap greps and would have filtered five of the nine tenders in the 10.10 scan
before any agent ran.
