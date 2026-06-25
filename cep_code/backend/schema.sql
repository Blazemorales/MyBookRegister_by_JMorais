-- TPE / CEP database schema
-- Compatible with PostgreSQL (Supabase / Render Postgres)

CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    username    TEXT UNIQUE NOT NULL,
    password    TEXT NOT NULL,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Amostras enviadas pelo usuário (payload bruto do JSON de upload).
CREATE TABLE IF NOT EXISTS amostras (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chart       TEXT NOT NULL,
    payload     JSONB NOT NULL,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS amostras_user_chart_idx
    ON amostras(user_id, chart);
CREATE INDEX IF NOT EXISTS amostras_user_recente_idx
    ON amostras(user_id, criado_em DESC);

-- Resultados do pipeline CEP por amostra/usuário/carta.
-- `dados` = JSON computado (lido em /results/cep/<chart>)
-- `pdf`   = binário do PDF (lido em /relatorio/<chart>)
CREATE TABLE IF NOT EXISTS resultados (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amostra_id  INTEGER REFERENCES amostras(id) ON DELETE CASCADE,
    chart       TEXT NOT NULL,
    dados       JSONB NOT NULL,
    pdf         BYTEA,
    gerado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS resultados_user_chart_recente_idx
    ON resultados(user_id, chart, gerado_em DESC);

-- Migração: a tabela antiga "relatorios" foi substituída por "resultados".
DROP TABLE IF EXISTS relatorios CASCADE;

-- Stream bruto das medições recebidas via Socket.IO (rpi_data → relatorio_data).
-- Append-only, alimenta o replay em subscribe_relatorio para clientes que
-- conectarem depois do dispositivo já estar emitindo.
-- Quando o volume crescer (>10M linhas), particionar por dia em received_at.
CREATE TABLE IF NOT EXISTS medicoes_stream (
    id          BIGSERIAL PRIMARY KEY,
    canal       TEXT NOT NULL DEFAULT 'default',
    chart       TEXT,
    payload     JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS medicoes_stream_canal_recente_idx
    ON medicoes_stream(canal, received_at DESC);
CREATE INDEX IF NOT EXISTS medicoes_stream_canal_data_idx
    ON medicoes_stream(canal, received_at);

-- Relatórios periódicos gerados pela Raspberry Pi (diário às 03:00 BRT e mensal).
CREATE TABLE IF NOT EXISTS relatorios_periodicos (
    id         BIGSERIAL PRIMARY KEY,
    tipo       TEXT NOT NULL,                  -- 'diario' | 'mensal'
    periodo    TEXT NOT NULL,                  -- '2026-06-23' ou '2026-06'
    canal      TEXT NOT NULL DEFAULT 'default',
    dados      JSONB NOT NULL,                 -- answer set + indicadores
    charts     JSONB,                          -- {carta: png_base64 ou url}
    pdf        BYTEA,
    gerado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tipo, periodo, canal)
);
CREATE INDEX IF NOT EXISTS relatorios_periodicos_tipo_periodo_idx
    ON relatorios_periodicos(tipo, periodo DESC);
