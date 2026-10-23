-- ============================================================================
-- match_name_city.sql — bridge tender WINNERS to a sendable company ADDRESS
-- Rebuilt and saved 23.10.2026. Previously this only ever existed inside a
-- background job, so it was lost every time. Do not let that happen again.
--
-- ⚠️ NOT YET EXECUTED. Written from the session that produced the 158 figure,
--    but the DB is unreachable from the dev machine (Hetzner-internal host,
--    SSH blocked), so this has NOT been run end to end. Expect to adjust
--    column names on first run — see "Columns assumed" below.
--
-- Expected result, from the run that produced the original numbers:
--     raw name match            ~70   (8% of 867)
--     normalised name          ~211   (24%)
--     normalised name + CITY   ~158   (18%)   <-- this query
-- The 53 that the city test removes are the dangerous ones. See Rule 3.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Rule 1  Never email a contracting authority.
--         960 of 2.835 rows in supplier_contacts were BUYER addresses
--         (625 gov.mk, 165 ЕЛЕМ, 137 universities, 25 procurement mailboxes,
--         8 Sobranie). Read v_sendable_contacts, never supplier_contacts.
-- Rule 2  Screen competitors by WHAT THEY WIN, never by company name.
--         MGGP S.A. is a Polish name with no Macedonian IT word in it and it
--         sailed through a name filter — but it wins
--         „Превентивно одржување и надградба на софтверска апликација".
--         It is a competitor. Only the subject of won contracts reveals that.
-- Rule 3  A name match without a city check is the WRONG RECIPIENT, not just
--         an imprecise one. „ПРОЛЕТЕР АС" (Скопје) matched
--         „ПРОЛЕТЕР АД с. Конопница, Крива Паланка" — a different company in
--         a different town. Writing to it would have been a letter to a
--         stranger about their business.
-- Rule 4  158 still needs a per-firm glance before the first send. The city
--         test catches a wrong city; it does NOT catch two similarly named
--         firms in the SAME city.
-- ---------------------------------------------------------------------------

-- Columns assumed (verify on first run):
--   tenders(winner_name, subject, publication_date, contract_value,
--           estimated_value, procuring_entity)   -- buyer is procuring_entity,
--                                                   NOT buyer_name (that is kg.tenders)
--   mk_companies(name, city, embs, edb)
--   v_sendable_contacts(company_name, email)     -- ~1.875 rows
-- There is NO tax-id bridge: tenders has no ЕДБ/ЕМБС for the winner, and
-- tender_bidders.company_tax_id is empty in all 51.258 rows. Hence name+city.

-- ---------------------------------------------------------------------------
-- norm_co(): strip legal-form noise so a long legal name can meet a short
-- trade name. „Друштво за трговија и услуги НИКОМ ГРУП ЛТД ДООЕЛ Скопје"
-- must reduce to the same core as the registry's „НИКОМ ГРУП".
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION norm_co(txt text) RETURNS text AS $$
  SELECT regexp_replace(
           regexp_replace(
             regexp_replace(
               upper(coalesce(txt, '')),
               -- leading descriptive phrases: „ДРУШТВО ЗА ТРГОВИЈА И УСЛУГИ "
               '^\s*(ДРУШТВО|ТРГОВСКО ДРУШТВО|ЈАВНО ПРЕТПРИЈАТИЕ|ЗАНАЕТЧИСКА)\s+[А-ШЊЉЏЃЌЅЈЕ\s]*?(ЗА\s+[А-ШЊЉЏЃЌЅЈЕ\s]+?)?(?=[А-ШЊЉЏЃЌЅЈЕ0-9]{2,}\s*(ДООЕЛ|ДОО|АД|ЛТД|$))',
               '', 'g'),
             -- legal forms and trade suffixes, anywhere
             '\m(ДООЕЛ|ДОО|АД|ДБ|ЛТД|LTD|УВОЗ-ИЗВОЗ|ЕКСПОРТ-ИМПОРТ|ЕКСПОРТ|ИМПОРТ|С\.П\.)\M',
             '', 'g'),
           '[^А-ШЊЉЏЃЌЅЈЕA-Z0-9]+', ' ', 'g')   -- collapse punctuation to spaces
$$ LANGUAGE sql IMMUTABLE;

-- quick sanity check, expect both sides equal:
--   SELECT norm_co('Друштво за трговија и услуги НИКОМ ГРУП ЛТД ДООЕЛ Скопје'),
--          norm_co('НИКОМ ГРУП');

-- ---------------------------------------------------------------------------
-- The bridge itself
-- ---------------------------------------------------------------------------
WITH won AS (                      -- the target band: real but not large
    SELECT t.winner_name AS legal_name,
           count(*)                                               AS wins,
           sum(coalesce(t.contract_value, t.estimated_value, 0))  AS total_12m
    FROM tenders t
    WHERE t.winner_name IS NOT NULL
      AND btrim(t.winner_name) <> ''
      AND t.publication_date >= current_date - interval '12 months'
    GROUP BY 1
    HAVING count(*) BETWEEN 2 AND 6
       AND sum(coalesce(t.contract_value, t.estimated_value, 0))
             BETWEEN 1500000 AND 15000000
),
it_firms AS (                      -- Rule 2: exclude by SUBJECT ever won
    SELECT DISTINCT winner_name
    FROM tenders
    WHERE winner_name IS NOT NULL
      AND (subject ILIKE '%софтвер%'        OR subject ILIKE '%апликациј%'
        OR subject ILIKE '%информацион%'    OR subject ILIKE '%информатич%'
        OR subject ILIKE '%веб%'            OR subject ILIKE '%web%'
        OR subject ILIKE '%ГИС%'            OR subject ILIKE '%лиценц%'
        OR subject ILIKE '%дигитализациј%'  OR subject ILIKE '%ИКТ%'
        OR subject ILIKE '%хардвер%'        OR subject ILIKE '%сервер%')
),
matched AS (
    SELECT w.legal_name,
           w.wins,
           w.total_12m,
           m.name  AS registry_name,
           m.city,
           m.embs,
           m.edb
    FROM won w
    JOIN mk_companies m
      ON norm_co(m.name) <> ''
     AND norm_co(w.legal_name) LIKE '%' || norm_co(m.name) || '%'
     -- Rule 3: the registry city must appear in the winner's legal name.
     -- This is what takes 211 down to 158 and kills the ПРОЛЕТЕР false match.
     AND m.city IS NOT NULL
     AND btrim(m.city) <> ''
     AND upper(w.legal_name) LIKE '%' || upper(btrim(m.city)) || '%'
    WHERE w.legal_name NOT IN (SELECT winner_name FROM it_firms)
)
SELECT DISTINCT ON (c.email)
       mt.legal_name,
       mt.registry_name,
       mt.city,
       mt.wins,
       mt.total_12m,
       round(mt.total_12m / nullif(mt.wins, 0))  AS avg_contract,
       c.email,
       mt.embs,
       mt.edb
FROM matched mt
JOIN v_sendable_contacts c           -- Rule 1: this view only, never supplier_contacts
  ON norm_co(c.company_name) = norm_co(mt.registry_name)
ORDER BY c.email, mt.total_12m DESC;

-- ---------------------------------------------------------------------------
-- Export for the outreach queue:
--   \copy (<the SELECT above>) TO 'prospects_158.csv' WITH (FORMAT csv, HEADER)
-- Drop the file in tenders/_scan/_service/ and the sending side needs no DB.
-- ---------------------------------------------------------------------------
