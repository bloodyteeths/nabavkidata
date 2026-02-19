# Lead Enrichment & Cold Outreach Plan

## Goal: 40,000+ Macedonia Emails → 50K EUR MRR

---

## PHASE 1: Lead Segmentation (Quality Tiers)

### Segment A: TENDER PARTICIPANTS (Highest Quality)
- **Source**: E-nabavki spider, suppliers table
- **Why high quality**: Actually participated in government tenders
- **Current count**: ~2,246 emails
- **Conversion expectation**: 3-4% (above average)
- **Message angle**: "We see you bid on [tender]. Here's how to win more."

### Segment B: APOLLO DECISION MAKERS (Medium Quality)
- **Source**: Apollo.io API
- **Why medium quality**: Decision makers in MK companies, but not tender-proven
- **Current count**: ~1,459 emails (enriching more)
- **Potential**: 6,855 total in Apollo
- **Conversion expectation**: 2-2.5%
- **Message angle**: "Macedonian companies are winning €X million in tenders. Are you?"

### Segment C: CENTRAL REGISTRY COMPANIES (Lower Quality)
- **Source**: Central Registry of Macedonia (crm.com.mk)
- **Why lower quality**: Just registered companies, unknown if relevant
- **Potential**: 70,000+ companies
- **Conversion expectation**: 1-1.5%
- **Message angle**: "Government spending €500M/year on tenders. Your competitors are bidding."

---

## PHASE 2: Data Collection Strategy

### Step 1: Maximize Apollo Data (No Email Credits Needed)
```
1. Pull ALL company details from Apollo:
   - Company name, domain, industry
   - Contact name, title, LinkedIn
   - Company size, location

2. Use Serper to find emails:
   - Search: "{name}" "{company}" email
   - Search: "{company}" Macedonia contact email
   - Extract domain, generate first.last@domain
```

### Step 2: Scrape Central Registry
```
1. Scrape crm.com.mk for all MK companies:
   - Company name, tax ID, address
   - Legal representative name
   - Registration date, status

2. Filter for active companies
3. Enrich with Serper for emails
```

### Step 3: Continuous E-nabavki Enrichment
```
1. Spider already collecting tender participants
2. Enrich new suppliers automatically
3. Highest priority segment
```

---

## PHASE 3: Database Schema for Outreach

### New Tables Needed:

```sql
-- Track all leads with segments
CREATE TABLE outreach_leads (
    lead_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(500),
    company_name VARCHAR(500),
    job_title VARCHAR(255),

    -- Segmentation
    segment CHAR(1) NOT NULL, -- A, B, C
    source VARCHAR(50), -- 'enabavki', 'apollo', 'central_registry'
    quality_score INT, -- 1-100

    -- Enrichment data
    company_domain VARCHAR(255),
    linkedin_url TEXT,
    phone VARCHAR(100),

    -- Outreach tracking
    outreach_status VARCHAR(50) DEFAULT 'not_contacted',
    -- 'not_contacted', 'email_1_sent', 'email_2_sent', 'replied', 'converted', 'unsubscribed'

    first_contact_at TIMESTAMP,
    last_contact_at TIMESTAMP,
    total_emails_sent INT DEFAULT 0,

    -- Response tracking
    opened_count INT DEFAULT 0,
    clicked_count INT DEFAULT 0,
    replied_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Track individual email sends
CREATE TABLE outreach_emails (
    email_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES outreach_leads(lead_id),

    campaign_name VARCHAR(100),
    email_sequence INT, -- 1, 2, 3 (which email in sequence)
    subject VARCHAR(500),

    sent_at TIMESTAMP,
    opened_at TIMESTAMP,
    clicked_at TIMESTAMP,
    replied_at TIMESTAMP,
    bounced BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Campaign definitions
CREATE TABLE outreach_campaigns (
    campaign_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    segment CHAR(1) NOT NULL, -- A, B, C

    email_1_subject TEXT,
    email_1_body TEXT,
    email_2_subject TEXT,
    email_2_body TEXT,
    email_3_subject TEXT,
    email_3_body TEXT,

    delay_days_1_to_2 INT DEFAULT 3,
    delay_days_2_to_3 INT DEFAULT 5,

    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_outreach_leads_email ON outreach_leads(email);
CREATE INDEX idx_outreach_leads_segment ON outreach_leads(segment);
CREATE INDEX idx_outreach_leads_status ON outreach_leads(outreach_status);
CREATE INDEX idx_outreach_emails_lead ON outreach_emails(lead_id);
```

---

## PHASE 4: Cold Email Sequences by Segment

### Segment A (Tender Participants) - 3 Email Sequence

**Email 1: Recognition**
```
Subject: Видов дека учествувавте на тендер за {cpv_category}

Здраво {first_name},

Забележав дека {company_name} учествуваше на јавни набавки.

Дали знаевте дека секој месец се објавуваат над 500 нови тендери
во Македонија вредни над €50 милиони?

Направивме платформа која ве известува за релевантни тендери
во вашата индустрија - пред вашата конкуренција.

Дали сакате да видите демо?
```

**Email 2: Value (Day 3)**
```
Subject: Вашите конкуренти веќе го користат ова

{first_name},

Компании како {competitor_1} и {competitor_2} веќе добиваат
известувања за нови тендери.

Еве што добивате:
✓ Дневни известувања за нови тендери
✓ AI анализа на тендерска документација
✓ Увид во конкуренција и нивни понуди

Првите 7 дена се бесплатни.

[Започни бесплатен пробен период]
```

**Email 3: Urgency (Day 8)**
```
Subject: Последна порака од мене

{first_name},

Ова е последната порака.

Ако јавните набавки не се приоритет за {company_name},
нема проблем.

Но ако сакате да бидете први кои ќе дознаат за нови можности -
јавете се.

Успех во бизнисот!
```

### Segment B (Apollo Decision Makers) - 3 Email Sequence

**Email 1: Opportunity**
```
Subject: €500M годишно во јавни набавки - учествувате ли?

Здраво {first_name},

Македонската влада троши над €500 милиони годишно преку
јавни набавки.

Видов дека {company_name} работи во {industry} -
секој месец има десетици тендери во вашата област.

Дали следите јавни набавки или тоа е нова можност за вас?

Можам да ви покажам какви тендери има за {industry}.
```

**Email 2: Social Proof (Day 4)**
```
Subject: Како {similar_company} доби договор од €{value}

{first_name},

Една компанија слична на вашата неодамна доби јавен договор
вреден €{value} за {category}.

Тие го најдоа тендерот преку нашата платформа.

Сакате да видите кои тендери се отворени за {industry}?
```

### Segment C (Central Registry) - 2 Email Sequence

**Email 1: Awareness**
```
Subject: Владата бара добавувачи од {city}

Здраво,

Владата и јавните институции постојано бараат добавувачи
за производи и услуги.

Дали знаевте дека компаниите од {city} можат да се
пријавуваат на тендери низ цела Македонија?

Направивме бесплатна листа на отворени тендери:
[Погледни отворени тендери]
```

---

## PHASE 5: Implementation Order

### Week 1: Infrastructure
- [ ] Create outreach database tables
- [ ] Build lead import script (deduplicate, segment)
- [ ] Set up email sending infrastructure

### Week 2: Segment A Campaign
- [ ] Import all e-nabavki leads to outreach_leads
- [ ] Mark existing contacts as "already contacted" if applicable
- [ ] Launch Segment A email sequence
- [ ] Monitor opens, clicks, replies

### Week 3: Apollo Enrichment + Segment B
- [ ] Pull remaining Apollo MK company data
- [ ] Enrich with Serper for emails
- [ ] Import to outreach_leads as Segment B
- [ ] Launch Segment B campaign

### Week 4: Central Registry + Segment C
- [ ] Scrape Central Registry
- [ ] Enrich with Serper
- [ ] Import as Segment C
- [ ] Launch Segment C campaign

---

## Key Rules

1. **NEVER contact same email twice** - Check outreach_leads before any send
2. **Respect unsubscribes** - Immediate removal from all campaigns
3. **Track everything** - Opens, clicks, replies for optimization
4. **Segment isolation** - Don't mix messaging between segments
5. **Quality over quantity** - Segment A gets priority and more follow-ups
