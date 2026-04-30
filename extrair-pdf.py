import sys
import json
import re

def extrair(pdf_path):
    try:
        import pdfplumber
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pdfplumber', '-q'])
        import pdfplumber

    produtos = []
    seen = set()

    def add(nome, tipo, valor):
        if not nome or valor < 0.01:
            return
        nome = nome.strip()[:80]
        k = nome[:20].lower() + '|' + str(round(valor))
        if k in seen:
            return
        seen.add(k)
        produtos.append({'nome': nome, 'tipo': tipo, 'valor': valor})

    def parse_val(s):
        if not s:
            return 0
        m = re.search(r'([\d.]+,\d{2})', s.replace(' ', ''))
        if not m:
            return 0
        try:
            return float(m.group(1).replace('.', '').replace(',', '.'))
        except:
            return 0

    def classifica_fundo(nome):
        n = nome.upper()
        if 'INFRA' in n or 'INCENTIVADO' in n or 'ELBRUS' in n:
            return 'Fundo Baixa Taxa'
        if 'SIMPLES' in n or 'CASH' in n or ('RF' in n and 'MULTIMERCADO' not in n):
            return 'Fundo Baixa Taxa'
        if 'MULTIMERCADO' in n or 'ADVISORY' in n or 'VERTEX' in n or 'QUEST' in n:
            return 'Fundo Alta Taxa'
        return 'Fundo Alta Taxa'

    def detecta_secao(words):
        """Detecta a seção da página pelo conteúdo — o cabeçalho é sempre igual em todas as páginas XP"""
        full = ' '.join(w['text'] for w in words).upper()

        # Ignora páginas de resumo/vencimentos/proventos — são duplicatas
        if re.search(r'PR[OÓ]XIMOS\s+VENCIMENTOS', full):
            return None
        if re.search(r'PROVENTO|DIVIDEND|JUROS\s+SOBRE\s+CAP', full[:400]):
            return None
        if re.search(r'SALDO\s+PROJETADO|EXTRATO\s+DE\s+MOVIMENTA', full[:400]):
            return None

        # Detecta pelo padrão "X% | Nome da Seção"
        if re.search(r'FUNDOS?\s+IMOBILI[AÁ]RIOS?', full) or re.search(r'FUNDOS?\s+LISTADOS?', full):
            return 'fii'
        if re.search(r'FUNDOS?\s+DE\s+INVESTIMENTO|FUNDOS?\s+DE\s+RENDA|FUNDOS?\s+MULTIMERCADO|FUNDOS?\s+DE\s+INFLA|FUNDOS?\s+DE\s+A[ÇC][OÕ]ES|FUNDOS?\s+ALTERNATIVO|FUNDOS?\s+GLOBAL|FUNDOS?\s+R[EV]\s', full):
            return 'fundo'
        if re.search(r'\bCOE\b|\bCERTIFICADO\s+DE\s+OPERA', full):
            return 'coe'
        if re.search(r'PREVID[EÊ]NCIA|VGBL|PGBL', full):
            return 'prev'
        # Ações: tem ticker pattern E coluna de cotação E não é proventos
        has_ticker  = bool(re.search(r'\b[A-Z]{4}\d{1,2}\b', full))
        has_cotacao = bool(re.search(r'[ÚU]LTIMA\s+COTA[ÇC][AÃ]O|PRE[ÇC]O\s+M[EÉ]DIO', full))
        if has_ticker and has_cotacao:
            return 'acoes'
        # Renda Fixa
        if re.search(r'\bCDB\b|\bLCI\b|\bLCA\b|\bCRI\b|\bCRA\b|\bCDCA\b|\bDEB\b|DEBENTURE|TESOURO', full):
            return 'rf'
        if re.search(r'RENDA\s+FIXA', full):
            return 'rf'

        return None

    TICKER = re.compile(r'^[A-Z]{4}\d{1,2}$')
    SKIP_RF = re.compile(
        r'^(Ativo|Aplica|Vencimento|Dispon|Garantia|Bloqueio|Valor|Posi|Taxa|Mercado|'
        r'Judicial|Carencia|POSI|DETALHADA|ATIVOS|Renda|Fixa|\d{2}/\d{2}/\d{4}|[A-Z]{3}/\d{4})$',
        re.I
    )
    meta = {}

    with pdfplumber.open(pdf_path) as pdf:
        total_pgs = len(pdf.pages)
        print(f"Total páginas: {total_pgs}")

        for pg_num, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            if not words:
                continue

            # Extrai meta da página 2 (resumo patrimonial)
            if pg_num == 2:
                full_text = ' '.join(w['text'] for w in words)
                m = re.search(r'Cliente:(.+?)Conta:(\d+)', full_text)
                if m:
                    meta['cliente'] = m.group(1).strip()
                    meta['conta']   = m.group(2).strip()
                m2 = re.search(r'Perfil:(\w+)', full_text)
                if m2:
                    meta['perfil'] = m2.group(1).strip()
                # Patrimônio, investimento, saldo
                rows = {}
                for w in words:
                    y = round(w['top'] / 3) * 3
                    if y not in rows: rows[y] = []
                    rows[y].append(w)
                for y, row in sorted(rows.items()):
                    row_s = sorted(row, key=lambda w: w['x0'])
                    line = ' '.join(w['text'] for w in row_s)
                    vals = re.findall(r'R\$\s*([\d.]+,\d{2})', line)
                    if len(vals) >= 3 and 100 <= y <= 140:
                        meta['patrimonio']  = parse_val(vals[0])
                        meta['investimento']= parse_val(vals[1])
                        meta['saldo_conta'] = parse_val(vals[2])

            # Detecta seção dinamicamente
            sec = detecta_secao(words)
            if not sec:
                continue

            print(f"PG {pg_num}: {sec}")

            # Agrupa por linha (top)
            rows = {}
            for w in words:
                y = round(w['top'] / 3) * 3
                if y not in rows: rows[y] = []
                rows[y].append(w)
            sorted_rows = sorted(rows.items())

            if sec in ('acoes', 'fii'):
                for y, row in sorted_rows:
                    row_s = sorted(row, key=lambda w: w['x0'])
                    first = row_s[0]['text'].strip()
                    if not TICKER.match(first):
                        continue
                    # Ignora linhas de proventos (x muito à direita ou linha muito curta)
                    val_words = [w for w in row_s if w['x0'] > 680]
                    if not val_words:
                        continue
                    v = parse_val(' '.join(w['text'] for w in val_words))
                    if v > 0:
                        tipo = 'FII' if sec == 'fii' else 'Acoes'
                        add(first, tipo, v)

            elif sec == 'rf':
                rf_name = []
                for y, row in sorted_rows:
                    row_s = sorted(row, key=lambda w: w['x0'])
                    val_words = [w for w in row_s if 670 <= w['x0'] <= 700]
                    if val_words:
                        v = parse_val(' '.join(w['text'] for w in val_words))
                        if v > 0 and rf_name:
                            nome = ' '.join(rf_name)
                            # Ignora cabeçalhos, totais e linhas de saldo
                            if not re.search(r'DETALHADA|ATIVOS|Renda Fixa|\d+[,.]\d+%|SALDO|RESGATE|PENDENTE|TERMOS', nome, re.I):
                                add(nome, 'Renda Fixa', v)
                        rf_name = []
                        continue
                    name_words = [w for w in row_s if w['x0'] < 200]
                    if not name_words:
                        continue
                    line = ' '.join(w['text'] for w in name_words).strip()
                    if line and not SKIP_RF.match(line) and not re.match(r'^\d+$', line):
                        rf_name.append(line)

            elif sec == 'fundo':
                for y, row in sorted_rows:
                    row_s = sorted(row, key=lambda w: w['x0'])
                    first = row_s[0]
                    if first['x0'] > 65:
                        continue
                    val_words = [w for w in row_s if 660 <= w['x0'] <= 695]
                    if not val_words:
                        continue
                    v = parse_val(' '.join(w['text'] for w in val_words))
                    if v <= 0:
                        continue
                    nome_completo = ' '.join(w['text'] for w in row_s if w['x0'] < 270).strip()
                    if len(nome_completo) < 3:
                        continue
                    SKIP = re.compile(r'^(Ativo|Data|Valor|Qtd|Em|Posi|Cota)$', re.I)
                    if SKIP.match(nome_completo):
                        continue
                    add(nome_completo, 'Fundo', v)

            elif sec == 'coe':
                for y, row in sorted_rows:
                    row_s = sorted(row, key=lambda w: w['x0'])
                    first = row_s[0]
                    if first['x0'] > 65:
                        continue
                    nome = ' '.join(w['text'] for w in row_s if w['x0'] < 320).strip()
                    if len(nome) < 4:
                        continue
                    SKIP = re.compile(r'^(Ativo|Emissor|Data|Vencimento|Qtd|Preco|Valor|Posi)$', re.I)
                    if SKIP.match(nome):
                        continue
                    val_words = [w for w in row_s if 668 <= w['x0'] <= 700]
                    if not val_words:
                        continue
                    v = parse_val(' '.join(w['text'] for w in val_words))
                    if v > 0:
                        add(nome, 'COE', v)

            elif sec == 'prev':
                for y, row in sorted_rows:
                    row_s = sorted(row, key=lambda w: w['x0'])
                    first = row_s[0]
                    if first['x0'] > 65:
                        continue
                    nome = ' '.join(w['text'] for w in row_s if w['x0'] < 270).strip()
                    if len(nome) < 4:
                        continue
                    SKIP = re.compile(r'^(Ativo|Data|Valor|Qtd|Em|Posi|Cota|Previd)$', re.I)
                    if SKIP.match(nome):
                        continue
                    val_words = [w for w in row_s if 660 <= w['x0'] <= 695]
                    if not val_words:
                        continue
                    v = parse_val(' '.join(w['text'] for w in val_words))
                    if v > 0:
                        add(nome, 'Previdência', v)

    # Aplica classificação correta dos fundos
    for p in produtos:
        if p['tipo'] == 'Fundo':
            p['tipo'] = classifica_fundo(p['nome'])

    # Adiciona saldo em conta
    if meta.get('saldo_conta', 0) > 0:
        add('Saldo em Conta', 'Saldo', meta['saldo_conta'])

    return produtos, meta


if __name__ == '__main__':
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\blank\Downloads\Posicao Detalhada - 3924287.pdf'
    json_out = sys.argv[2] if len(sys.argv) > 2 else 'carteira-extraida.json'

    produtos, meta = extrair(pdf_path)

    print(f"\nCliente: {meta.get('cliente','?')} | Conta: {meta.get('conta','?')}")
    print(f"Patrimônio: R$ {meta.get('patrimonio',0):,.2f}")
    print(f"\n=== {len(produtos)} PRODUTOS ===")
    for p in produtos:
        print(f"[{p['tipo']}] {p['nome']} = R$ {p['valor']:,.2f}")

    total = sum(p['valor'] for p in produtos)
    print(f"\nTotal extraído: R$ {total:,.2f}")

    resultado = {
        'produtos': produtos,
        'meta': meta,
        'resumo': {'total': total}
    }
    with open(json_out, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"Salvo em {json_out}")
