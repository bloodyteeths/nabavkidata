-- Migration: Lead Enrichment and Outreach System
-- Date: 2025-12-13
-- Purpose: Add tables for supplier contact enrichment, outreach campaigns, and suppression

-- ============================================================================
-- SUPPLIER CONTACTS - Enriched contact information for suppliers
-- ============================================================================

CREATE TABLE IF NOT EXISTS supplier_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id UUID NOT NULL REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    email_type VARCHAR(20) NOT NULL DEFAULT 'unknown', -- role_based, personal, unknown
    source_url TEXT,
    source_domain VARCHAR(255),
    confidence_score INTEGER DEFAULT 50 CHECK (confidence_score >= 0 AND confidence_score <= 100),
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_verified_at TIMESTAMP,
    status VARCHAR(30) NOT NULL DEFAULT 'new', -- new, verified, invalid, bounced, unsubscribed, do_not_contact
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for supplier_contacts
CREATE INDEX IF NOT EXISTS idx_supplier_contacts_supplier_id ON supplier_contacts(supplier_id);
CREATE INDEX IF NOT EXISTS idx_supplier_contacts_email ON supplier_contacts(email);
CREATE INDEX IF NOT EXISTS idx_supplier_contacts_status ON supplier_contacts(status);
CREATE INDEX IF NOT EXISTS idx_supplier_contacts_email_type ON supplier_contacts(email_type);
CREATE INDEX IF NOT EXISTS idx_supplier_contacts_confidence ON supplier_contacts(confidence_score);
CREATE UNIQUE INDEX IF NOT EXISTS idx_supplier_contacts_unique_email ON supplier_contacts(supplier_id, email);

-- ============================================================================
-- OUTREACH MESSAGES - Track all outreach campaign messages
-- ============================================================================

CREATE TABLE IF NOT EXISTS outreach_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id UUID NOT NULL REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES supplier_contacts(id) ON DELETE CASCADE,
    campaign_id VARCHAR(100) NOT NULL DEFAULT 'default',
    sequence_step INTEGER NOT NULL DEFAULT 0, -- 0=initial, 1=followup1, 2=followup2
    subject VARCHAR(500),
    template_version VARCHAR(50),
    personalization JSONB, -- {supplier_name, top_cpv_categories, recent_awards_count, example_tender, value_pitch, segment}
    postmark_message_id VARCHAR(255),
    status VARCHAR(30) NOT NULL DEFAULT 'queued', -- queued, sent, delivered, bounced, complained, opened, clicked, replied, stopped
    sent_at TIMESTAMP,
    last_event_at TIMESTAMP,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for outreach_messages
CREATE INDEX IF NOT EXISTS idx_outreach_messages_supplier_id ON outreach_messages(supplier_id);
CREATE INDEX IF NOT EXISTS idx_outreach_messages_contact_id ON outreach_messages(contact_id);
CREATE INDEX IF NOT EXISTS idx_outreach_messages_status ON outreach_messages(status);
CREATE INDEX IF NOT EXISTS idx_outreach_messages_campaign_id ON outreach_messages(campaign_id);
CREATE INDEX IF NOT EXISTS idx_outreach_messages_postmark_id ON outreach_messages(postmark_message_id);
CREATE INDEX IF NOT EXISTS idx_outreach_messages_sent_at ON outreach_messages(sent_at);

-- ============================================================================
-- SUPPRESSION LIST - Global email suppression for compliance
-- ============================================================================

CREATE TABLE IF NOT EXISTS suppression_list (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    reason VARCHAR(50) NOT NULL, -- unsubscribed, bounce, complaint, manual
    source VARCHAR(100), -- Where the suppression came from (postmark, user_request, admin)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- Indexes for suppression_list
CREATE UNIQUE INDEX IF NOT EXISTS idx_suppression_list_email ON suppression_list(email);
CREATE INDEX IF NOT EXISTS idx_suppression_list_reason ON suppression_list(reason);
CREATE INDEX IF NOT EXISTS idx_suppression_list_created_at ON suppression_list(created_at);

-- ============================================================================
-- OUTREACH TEMPLATES - Store email templates with versions
-- ============================================================================

CREATE TABLE IF NOT EXISTS outreach_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    sequence_step INTEGER NOT NULL DEFAULT 0,
    segment VARCHAR(50) NOT NULL, -- frequent_winner, occasional, new_unknown, all
    subject_variants JSONB NOT NULL DEFAULT '[]'::jsonb, -- ["Subject 1", "Subject 2"]
    body_html TEXT NOT NULL,
    body_text TEXT,
    version VARCHAR(20) NOT NULL DEFAULT 'v1',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for outreach_templates
CREATE INDEX IF NOT EXISTS idx_outreach_templates_segment ON outreach_templates(segment);
CREATE INDEX IF NOT EXISTS idx_outreach_templates_step ON outreach_templates(sequence_step);
CREATE INDEX IF NOT EXISTS idx_outreach_templates_active ON outreach_templates(is_active);

-- ============================================================================
-- ENRICHMENT JOBS - Track enrichment job status
-- ============================================================================

CREATE TABLE IF NOT EXISTS enrichment_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id UUID NOT NULL REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    status VARCHAR(30) NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed
    search_queries JSONB,
    results_count INTEGER DEFAULT 0,
    emails_found INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for enrichment_jobs
CREATE INDEX IF NOT EXISTS idx_enrichment_jobs_supplier_id ON enrichment_jobs(supplier_id);
CREATE INDEX IF NOT EXISTS idx_enrichment_jobs_status ON enrichment_jobs(status);
CREATE INDEX IF NOT EXISTS idx_enrichment_jobs_created_at ON enrichment_jobs(created_at);

-- ============================================================================
-- UPDATE TRIGGER for updated_at columns
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_supplier_contacts_updated_at ON supplier_contacts;
CREATE TRIGGER update_supplier_contacts_updated_at
    BEFORE UPDATE ON supplier_contacts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_outreach_messages_updated_at ON outreach_messages;
CREATE TRIGGER update_outreach_messages_updated_at
    BEFORE UPDATE ON outreach_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_outreach_templates_updated_at ON outreach_templates;
CREATE TRIGGER update_outreach_templates_updated_at
    BEFORE UPDATE ON outreach_templates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- INSERT DEFAULT OUTREACH TEMPLATES
-- ============================================================================

INSERT INTO outreach_templates (name, sequence_step, segment, subject_variants, body_html, body_text, version)
VALUES
(
    'Initial Outreach - Frequent Winners',
    0,
    'frequent_winner',
    '["Следете ја конкуренцијата во јавни набавки", "Како {{supplier_name}} може да победи повеќе тендери"]'::jsonb,
    '<p>Почитувани,</p>
<p>Забележавме дека {{supplier_name}} има <strong>{{recent_awards_count}} победи</strong> во последните 12 месеци во категорија {{top_cpv_categories}}.</p>
<p>NabavkiData ви овозможува:</p>
<ul>
<li>Следење на конкурентски понуди во реално време</li>
<li>AI анализа на тендерска документација</li>
<li>Известувања за нови тендери во вашите категории</li>
</ul>
<p>Пример: Неодамна {{example_tender}}</p>
<p><a href="https://nabavkidata.com/?utm_source=outreach&utm_campaign=frequent_winner">Започнете бесплатно</a></p>
<p>Поздрав,<br>Тимот на NabavkiData</p>
<hr>
<p style="font-size:12px;color:#666;">Ако не сакате да добивате вакви пораки, <a href="{{unsubscribe_url}}">кликнете тука за одјава</a>.</p>',
    'Почитувани,

Забележавме дека {{supplier_name}} има {{recent_awards_count}} победи во последните 12 месеци во категорија {{top_cpv_categories}}.

NabavkiData ви овозможува:
- Следење на конкурентски понуди во реално време
- AI анализа на тендерска документација
- Известувања за нови тендери во вашите категории

Започнете бесплатно: https://nabavkidata.com/?utm_source=outreach&utm_campaign=frequent_winner

Поздрав,
Тимот на NabavkiData

---
Ако не сакате да добивате вакви пораки, одјавете се тука: {{unsubscribe_url}}',
    'v1'
),
(
    'Initial Outreach - Occasional Participants',
    0,
    'occasional',
    '["Пропуштате тендери во {{top_cpv_categories}}?", "AI известувања за тендери - NabavkiData"]'::jsonb,
    '<p>Почитувани,</p>
<p>Гледаме дека {{supplier_name}} учествува во јавни набавки во категорија {{top_cpv_categories}}.</p>
<p>Дали знаевте дека неодамна имаше {{recent_tenders_count}} нови тендери во оваа област?</p>
<p>NabavkiData ви помага да:</p>
<ul>
<li>Никогаш не пропуштите релевантен тендер</li>
<li>Добиете AI извлечени барања од документација</li>
<li>Споредите цени и понуди</li>
</ul>
<p><a href="https://nabavkidata.com/?utm_source=outreach&utm_campaign=occasional">Пробајте бесплатно</a></p>
<p>Поздрав,<br>Тимот на NabavkiData</p>
<hr>
<p style="font-size:12px;color:#666;">За одјава од маркетинг пораки: <a href="{{unsubscribe_url}}">одјави се</a></p>',
    'Почитувани,

Гледаме дека {{supplier_name}} учествува во јавни набавки во категорија {{top_cpv_categories}}.

Дали знаевте дека неодамна имаше нови тендери во оваа област?

NabavkiData ви помага да:
- Никогаш не пропуштите релевантен тендер
- Добиете AI извлечени барања од документација
- Споредите цени и понуди

Пробајте бесплатно: https://nabavkidata.com/?utm_source=outreach&utm_campaign=occasional

Поздрав,
Тимот на NabavkiData

---
За одјава: {{unsubscribe_url}}',
    'v1'
),
(
    'Initial Outreach - New/Unknown',
    0,
    'new_unknown',
    '["Бесплатен мини-извештај за вашите тендерски можности", "Дознајте кои тендери се релевантни за вас"]'::jsonb,
    '<p>Почитувани,</p>
<p>Забележавме дека {{supplier_name}} е активна компанија во Македонија.</p>
<p>Дали сте заинтересирани за јавни набавки? NabavkiData може да ви помогне да:</p>
<ul>
<li>Најдете релевантни тендери за вашата дејност</li>
<li>Добиете известувања за нови можности</li>
<li>Анализирате конкуренција</li>
</ul>
<p><a href="https://nabavkidata.com/?utm_source=outreach&utm_campaign=new">Започнете бесплатно</a></p>
<p>Поздрав,<br>Тимот на NabavkiData</p>
<hr>
<p style="font-size:12px;color:#666;"><a href="{{unsubscribe_url}}">Одјава од маркетинг пораки</a></p>',
    'Почитувани,

Забележавме дека {{supplier_name}} е активна компанија во Македонија.

Дали сте заинтересирани за јавни набавки? NabavkiData може да ви помогне да:
- Најдете релевантни тендери за вашата дејност
- Добиете известувања за нови можности
- Анализирате конкуренција

Започнете бесплатно: https://nabavkidata.com/?utm_source=outreach&utm_campaign=new

Поздрав,
Тимот на NabavkiData

---
Одјава: {{unsubscribe_url}}',
    'v1'
),
(
    'Follow-up 1',
    1,
    'all',
    '["Уште ја разгледувате платформата?", "Бесплатен пристап до NabavkiData"]'::jsonb,
    '<p>Почитувани,</p>
<p>Пред неколку дена ви испративме информација за NabavkiData.</p>
<p>Само да потсетиме - може бесплатно да:</p>
<ul>
<li>Прегледате сите активни тендери</li>
<li>Поставите известувања за вашите категории</li>
<li>Испробате AI анализа</li>
</ul>
<p><a href="https://nabavkidata.com/?utm_source=outreach&utm_campaign=followup1">Регистрирајте се бесплатно</a></p>
<p>Поздрав,<br>Тимот на NabavkiData</p>
<hr>
<p style="font-size:12px;color:#666;"><a href="{{unsubscribe_url}}">Одјава</a></p>',
    'Почитувани,

Пред неколку дена ви испративме информација за NabavkiData.

Само да потсетиме - може бесплатно да:
- Прегледате сите активни тендери
- Поставите известувања за вашите категории
- Испробате AI анализа

Регистрирајте се: https://nabavkidata.com/?utm_source=outreach&utm_campaign=followup1

Поздрав,
Тимот на NabavkiData

---
Одјава: {{unsubscribe_url}}',
    'v1'
),
(
    'Follow-up 2 - Final',
    2,
    'all',
    '["Последна можност за бесплатен пробен период", "Не ја пропуштајте оваа понуда"]'::jsonb,
    '<p>Почитувани,</p>
<p>Ова е наша последна порака.</p>
<p>Ако сте заинтересирани за следење на јавни набавки во Македонија, NabavkiData е тука за вас.</p>
<p><a href="https://nabavkidata.com/?utm_source=outreach&utm_campaign=followup2">Пробајте бесплатно</a></p>
<p>Ви посакуваме успех во вашиот бизнис!</p>
<p>Поздрав,<br>Тимот на NabavkiData</p>
<hr>
<p style="font-size:12px;color:#666;"><a href="{{unsubscribe_url}}">Одјава</a></p>',
    'Почитувани,

Ова е наша последна порака.

Ако сте заинтересирани за следење на јавни набавки во Македонија, NabavkiData е тука за вас.

Пробајте бесплатно: https://nabavkidata.com/?utm_source=outreach&utm_campaign=followup2

Ви посакуваме успех во вашиот бизнис!

Поздрав,
Тимот на NabavkiData

---
Одјава: {{unsubscribe_url}}',
    'v1'
)
ON CONFLICT DO NOTHING;
