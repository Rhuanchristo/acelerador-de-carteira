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
    meta = {}

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
        # Fundos de infraestrutura incentivados = baixa taxa
        if 'INFRA' in n or 'INCENTIVADO' in n or 'ELBRUS' in n:
            return 'Fundo Baixa Taxa'
        # Fundos de renda fixa simples = baixa taxa
        if 'SIMPLES' in n or 'CASH' in n or 'RF' in n or 'RENDA FIXA' in n:
            return 'Fundo Baixa Taxa'
        # Fundos multimercado advisory = alta taxa
        if 'MULTIMERCADO' in n or 'ADVISORY' in n or 'VERTEX' in n or 'QUEST' in n:
            return 'Fundo Alta Taxa'
        return 'Fundo Alta Taxa'

    SKIP_RF = re.compile(
        r'^(Ativo|Aplica|Vencimento|Dispon|Garantia|Bloqueio|Valor|Posi|Taxa|Mercado|'
        r'Judicial|Carencia|POSI|DETALHADA|ATIVOS|Renda|Fixa|\d{2}/\d{2}/\d{4}|[A-Z]{3}/\d{4})$',
        re.I
    )

    with pdfplumber.open(pdf_path) as pdf:
        for pg_num, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            if not words:
                continue

            # Agrupa por top (y) com tolerancia 3px
            rows = {}
            for w in words:
                y = round(w['top'] / 3) * 3
                if y not in rows:
                    rows[y] = []
                rows[y].append(w)
            sorted_rows = sorted(rows.items())

            # Pagina 2: extrai meta dados (cliente, patrimonio, saldo)
            if pg_num == 2:
                for y, row in sorted_rows:
                    row_s = sorted(row, key=lambda w: w['x0'])
                    line = ' '.join(w['text'] for w in row_s)
                    # Cliente e conta
                    if 'Cliente:' in line:
                        m = re.search(r'Cliente:(.+?)Conta:(\d+)', line)
                        if m:
                            meta['cliente'] = m.group(1).strip()
                            meta['conta'] = m.group(2).strip()
                        m2 = re.search(r'Perfil:(\w+)', line)
                        if m2:
                            meta['perfil'] = m2.group(1).strip()
                    # Patrimonio, investimento, saldo
                    if y == round(120/3)*3 or (120 <= y <= 126):
                        vals = re.findall(r'R\$\s*([\d.]+,\d{2})', line)
                        if len(vals) >= 3:
                            meta['patrimonio'] = parse_val('R$ ' + vals[0])
                            meta['investimento'] = parse_val('R$ ' + vals[1])
                            meta['saldo_conta'] = parse_val('R$ ' + vals[2])
                        elif len(vals) == 1:
                            # Valores podem estar em palavras separadas
                            pass

            is_acoes  = pg_num in [2, 3]
            is_rf     = pg_num in [5, 6]
            is_fundos = pg_num in [7, 8, 9]
            is_coe    = pg_num == 10
            is_fii    = pg_num == 11
            if not any([is_acoes, is_rf, is_fundos, is_coe, is_fii]):
                continue

            if is_acoes or is_fii:
                TICKER = re.compile(r'^[A-Z]{4}\d{1,2}$')
                for y, row in sorted_rows:
                    row_s = sorted(row, key=lambda w: w['x0'])
                    first = row_s[0]['text'].strip()
                    if not TICKER.match(first):
                        continue
                    val_words = [w for w in row_s if w['x0'] > 680]
                    if not val_words:
                        continue
                    val_str = ' '.join(w['text'] for w in val_words)
                    v = parse_val(val_str)
                    if v > 0:
                        tipo = 'FII' if is_fii else 'Acoes'
                        add(first, tipo, v)

            elif is_rf:
                rf_name = []
                for y, row in sorted_rows:
                    row_s = sorted(row, key=lambda w: w['x0'])
                    val_words = [w for w in row_s if 670 <= w['x0'] <= 700]
                    if val_words:
                        v = parse_val(' '.join(w['text'] for w in val_words))
                        if v > 0 and rf_name:
                            nome = ' '.join(rf_name)
                            if not re.search(r'DETALHADA|ATIVOS|Renda Fixa|\d+[,.]\d+%', nome, re.I):
                                add(nome, 'Renda Fixa', v)
                        rf_name = []
                        continue
                    name_words = [w for w in row_s if w['x0'] < 200]
                    if not name_words:
                        continue
                    line = ' '.join(w['text'] for w in name_words).strip()
                    if line and not SKIP_RF.match(line) and not re.match(r'^\d+$', line):
                        rf_name.append(line)

            elif is_fundos:
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

            elif is_coe:
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

    # Adiciona saldo em conta se disponivel
    if meta.get('saldo_conta', 0) > 0:
        add('Saldo em Conta', 'Saldo', meta['saldo_conta'])

    # Aplica classificacao correta dos fundos
    for p in produtos:
        if p['tipo'] == 'Fundo':
            p['tipo'] = classifica_fundo(p['nome'])

    return produtos, meta


if __name__ == '__main__':
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\blank\Downloads\Posicao Detalhada - 3924287.pdf'
    json_out = sys.argv[2] if len(sys.argv) > 2 else 'carteira-extraida.json'

    produtos, meta = extrair(pdf_path)

    total = sum(p['valor'] for p in produtos)
    for p in produtos:
        print(f"[{p['tipo']}] {p['nome']} = R$ {p['valor']:,.2f}")
    print(f"\nTotal: {len(produtos)} produtos = R$ {total:,.2f}")

    resultado = {
        'produtos': produtos,
        'meta': meta,
        'resumo': {'total': total}
    }
    with open(json_out, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"Salvo em {json_out}")
