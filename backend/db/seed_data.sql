-- Seed Data for Development/Testing
-- Purpose: Provide sample data for local development
-- Date: 2024-11-22

-- Sample users (passwords are bcrypt hash of "password123")
INSERT INTO users (user_id, email, password_hash, full_name, subscription_tier, email_verified) VALUES
('11111111-1111-1111-1111-111111111111', 'admin@nabavkidata.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyWui/WJge7O', 'Admin User', 'enterprise', TRUE),
('22222222-2222-2222-2222-222222222222', 'user@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyWui/WJge7O', 'Test User', 'free', TRUE),
('33333333-3333-3333-3333-333333333333', 'pro@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyWui/WJge7O', 'Pro User', 'pro', TRUE);

-- Sample tenders
INSERT INTO tenders (tender_id, title, description, category, procuring_entity, opening_date, closing_date, estimated_value_mkd, estimated_value_eur, cpv_code, status) VALUES
('2024/001', 'Набавка на компјутерска опрема', 'Набавка на 50 компјутери, монитори и печатачи за Министерството за образование', 'IT Equipment', 'Министерство за образование и наука', '2024-01-15', '2024-02-15', 3075000, 50000, '30213100-6', 'open'),
('2024/002', 'Изградба на локален пат', 'Реконструкција на локален пат во должина од 5km', 'Construction', 'Општина Скопје', '2024-01-20', '2024-02-20', 12300000, 200000, '45233140-2', 'open'),
('2024/003', 'Медицинска опрема за болница', 'Набавка на дијагностичка опрема за Клиничка болница', 'Medical Equipment', 'Министерство за здравство', '2024-01-10', '2024-02-10', 6150000, 100000, '33100000-1', 'closed');

-- Sample documents
INSERT INTO documents (doc_id, tender_id, doc_type, file_name, content_text, extraction_status) VALUES
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '2024/001', 'Specification', 'spec_2024_001.pdf', 'Техничка спецификација за набавка на компјутерска опрема. Потребни се следниве артикли: 1. Desktop компјутери - 50 парчиња со минимум спецификации Intel i5, 16GB RAM, 512GB SSD. 2. Монитори 24 инчи - 50 парчиња. 3. Ласерски печатачи - 10 парчиња.', 'success'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '2024/002', 'Specification', 'spec_2024_002.pdf', 'Проектна документација за реконструкција на локален пат. Должина 5km, ширина 6m, асфалтна подлога. Рок на изведба: 6 месеци.', 'success');

-- Sample alerts
INSERT INTO alerts (alert_id, user_id, name, filters, frequency, is_active) VALUES
('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', '33333333-3333-3333-3333-333333333333', 'IT Equipment Alerts', '{"category": "IT Equipment", "min_value": 10000}', 'daily', TRUE);

-- Sample usage tracking
INSERT INTO usage_tracking (user_id, action_type) VALUES
('22222222-2222-2222-2222-222222222222', 'tender_search'),
('22222222-2222-2222-2222-222222222222', 'ai_query'),
('33333333-3333-3333-3333-333333333333', 'ai_query');
