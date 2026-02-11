-- ============================================
-- 002_seed.sql — Начальные данные
-- ============================================

-- Billing Plans
INSERT INTO billing_plans (id, name, price_monthly, max_api_keys, max_sessions, max_sub_users, features) VALUES
    ('e0000000-0000-0000-0000-000000000001', 'free', 0, 1, 1, 1, '{"description": "Бесплатный тариф"}'),
    ('e0000000-0000-0000-0000-000000000002', 'starter', 990, 3, 5, 3, '{"description": "Начальный тариф"}'),
    ('e0000000-0000-0000-0000-000000000003', 'pro', 2990, 10, 20, 10, '{"description": "Профессиональный тариф"}')
ON CONFLICT (name) DO NOTHING;

-- Default Supervisor (для dev/test)
INSERT INTO supervisors (id, name, email) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'DevSupervisor', 'dev@zipmobile.ru')
ON CONFLICT (id) DO NOTHING;
