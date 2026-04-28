-- ══════════════════════════════════════════════════════════
-- Acelerador Patrimonial — Tabela de Leads com RLS
-- Execute no Supabase SQL Editor: Dashboard → SQL Editor → New Query
-- ══════════════════════════════════════════════════════════

-- 1. Tabela de leads
CREATE TABLE IF NOT EXISTS public.leads (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  nome             text        NOT NULL CHECK (char_length(nome) BETWEEN 2 AND 100),
  email            text        NOT NULL CHECK (email ~* '^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$'),
  tel              text        CHECK (char_length(tel) <= 20),
  faixa_patrimonio text        CHECK (faixa_patrimonio IN ('ate300k', '300k-1M', '1M-5M', 'acima5M')),
  criado_em        timestamptz NOT NULL DEFAULT now()
);

-- 2. Habilita RLS
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;

-- 3. Políticas RLS

-- Anônimo pode inserir (lead público vindo do formulário)
CREATE POLICY "leads: insert público"
  ON public.leads
  FOR INSERT
  TO anon
  WITH CHECK (true);

-- Apenas usuários autenticados (assessores logados) podem ler
CREATE POLICY "leads: leitura autenticada"
  ON public.leads
  FOR SELECT
  TO authenticated
  USING (true);

-- Ninguém pode atualizar via API (apenas service_role via backend)
CREATE POLICY "leads: sem update"
  ON public.leads
  FOR UPDATE
  TO anon, authenticated
  USING (false);

-- Ninguém pode deletar via API (apenas service_role via backend)
CREATE POLICY "leads: sem delete"
  ON public.leads
  FOR DELETE
  TO anon, authenticated
  USING (false);

-- 4. Índices para performance
CREATE INDEX IF NOT EXISTS leads_email_idx      ON public.leads (email);
CREATE INDEX IF NOT EXISTS leads_criado_em_idx  ON public.leads (criado_em DESC);

-- 5. Opcional: revoke acesso direto à tabela para o role anon (só via RLS)
REVOKE ALL ON public.leads FROM anon;
GRANT INSERT ON public.leads TO anon;
REVOKE ALL ON public.leads FROM authenticated;
GRANT SELECT ON public.leads TO authenticated;

-- ══════════════════════════════════════════════════════════
-- Após executar:
-- 1. Vá em Authentication → URL Configuration e adicione seu domínio
-- 2. Em Settings → API, copie a URL e a anon key
-- 3. Cole em cadastro.html: SUPABASE_URL e SUPABASE_KEY
-- 4. Configure CORS em Settings → API → Allowed Origins
-- ══════════════════════════════════════════════════════════
