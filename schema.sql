-- TPE / CEP database schema
-- Compatible with PostgreSQL (Supabase)

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS amostras (
    id SERIAL PRIMARY KEY,
    chart TEXT NOT NULL,
    n_amostra INTEGER,
    limite_sup_esp NUMERIC,
    limite_inf_esp NUMERIC,
    measurements JSONB NOT NULL,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS relatorios (
    id SERIAL PRIMARY KEY,
    amostra_id INTEGER REFERENCES amostras(id) ON DELETE CASCADE,
    chart TEXT NOT NULL,
    resultado JSONB NOT NULL,
    gerado_em TIMESTAMPTZ DEFAULT NOW()
);
