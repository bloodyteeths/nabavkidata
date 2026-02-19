-- Migration: Create contacts table for admin outreach
-- Purpose: Store unique contact information from tenders for marketing/announcements

-- Create contacts table
CREATE TABLE IF NOT EXISTS contacts (
    contact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Contact type: 'procuring_entity', 'winner', 'bidder'
    contact_type VARCHAR(50) NOT NULL,

    -- Entity/Company information
    entity_name VARCHAR(500) NOT NULL,
    entity_type VARCHAR(100),  -- 'government', 'company', 'institution'

    -- Contact details
    email VARCHAR(255),
    phone VARCHAR(100),
    address TEXT,
    city VARCHAR(200),
    contact_person VARCHAR(255),

    -- Source tracking
    source_tender_id VARCHAR(100),
    source_url TEXT,

    -- Status for outreach
    status VARCHAR(50) DEFAULT 'new',  -- new, contacted, subscribed, unsubscribed
    notes TEXT,

    -- Timestamps
    scraped_at TIMESTAMP DEFAULT NOW(),
    last_contacted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(contact_type);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_entity ON contacts(entity_name);
CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);

-- Unique constraint on email to avoid duplicates
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_unique_email
ON contacts(email) WHERE email IS NOT NULL AND email != '';

-- Populate contacts from existing tender data
-- 1. Procuring entities (government institutions with contact info)
INSERT INTO contacts (contact_type, entity_name, entity_type, email, phone, contact_person, source_tender_id, source_url)
SELECT DISTINCT ON (contact_email)
    'procuring_entity' as contact_type,
    procuring_entity as entity_name,
    'government' as entity_type,
    contact_email as email,
    contact_phone as phone,
    contact_person,
    tender_id as source_tender_id,
    source_url
FROM tenders
WHERE contact_email IS NOT NULL
  AND contact_email != ''
  AND procuring_entity IS NOT NULL
ON CONFLICT (email) DO NOTHING;

-- 2. Winners (companies that won tenders)
INSERT INTO contacts (contact_type, entity_name, entity_type, source_tender_id, source_url)
SELECT DISTINCT ON (winner)
    'winner' as contact_type,
    winner as entity_name,
    'company' as entity_type,
    tender_id as source_tender_id,
    source_url
FROM tenders
WHERE winner IS NOT NULL
  AND winner != ''
ON CONFLICT DO NOTHING;

-- 3. Also insert from suppliers table if it has data
INSERT INTO contacts (contact_type, entity_name, entity_type, email, phone, address, city, contact_person)
SELECT DISTINCT ON (company_name)
    'winner' as contact_type,
    company_name as entity_name,
    'company' as entity_type,
    contact_email as email,
    contact_phone as phone,
    address,
    city,
    contact_person
FROM suppliers
WHERE company_name IS NOT NULL
ON CONFLICT DO NOTHING;

-- Show summary
DO $$
DECLARE
    total_count INTEGER;
    with_email INTEGER;
    procuring_count INTEGER;
    winner_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_count FROM contacts;
    SELECT COUNT(*) INTO with_email FROM contacts WHERE email IS NOT NULL AND email != '';
    SELECT COUNT(*) INTO procuring_count FROM contacts WHERE contact_type = 'procuring_entity';
    SELECT COUNT(*) INTO winner_count FROM contacts WHERE contact_type = 'winner';

    RAISE NOTICE 'Contacts table populated:';
    RAISE NOTICE '  Total contacts: %', total_count;
    RAISE NOTICE '  With email: %', with_email;
    RAISE NOTICE '  Procuring entities: %', procuring_count;
    RAISE NOTICE '  Winners: %', winner_count;
END $$;
