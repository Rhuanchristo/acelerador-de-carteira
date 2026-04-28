import PyPDF2
import re
import json
import sys

def extrair_posicao_detalhada(pdf_path):
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            texto_completo = ""

            # Extrair texto de todas as páginas
            print(f"Processando {len(pdf_reader.pages)} páginas...")
            for i, page in enumerate(pdf_reader.pages, 1):
                texto_completo += f"\n--- PÁGINA {i} ---\n"
                texto_completo += page.extract_text() + "\n"

            # Limpar caracteres problemáticos
            texto_completo = texto_completo.encode('ascii', 'ignore').decode('ascii')

            linhas = texto_completo.split('\n')
            produtos = []

            # Padrões para identificar valores monetários
            padrao_valor = re.compile(r'R?\$?\s*([\d.,]+(?:\.\d{3})*,\d{2})')

            # Padrões para identificar tipos de produtos
            padroes_rf = ['CDB', 'LCI', 'LCA', 'TESOURO', 'DEBENTURE', 'CRI', 'CRA', 'RENDA FIXA', 'XP CRIPTO', 'BANCO']
            padroes_rv = ['AÇÕES', 'AÇÃO', 'FII', 'FUNDO', 'ETF', 'BDR', 'RENDA VARIÁVEL']
            padroes_acoes = ['3', '4', '5', '6', '11']  # Sufixos de ações

            # Palavras a ignorar
            skip_words = ['TOTAL', 'SUBTOTAL', 'PATRIMONIO', 'INVESTIMENTO', 'SALDO', 'DISPONIVEL',
                         'POSICAO', 'CONSOLIDADA', 'DETALHADA', 'PRECIFICACAO', 'MERCADO',
                         'QUANTIDADE', 'PRECO', 'COTACAO', 'RENTABILIDADE', 'VENCIMENTO',
                         'CUSTODIA', 'REMUNERADA', 'PAPEL', 'FINANCEIRO', 'ULTIMA']

            produtos_vistos = set()
            linha_anterior = ""

            for i, linha in enumerate(linhas):
                linha_upper = linha.upper().strip()

                # Pula linhas vazias ou muito curtas
                if len(linha_upper) < 3:
                    linha_anterior = linha
                    continue

                # Pula cabeçalhos e totais
                if any(skip in linha_upper for skip in skip_words):
                    linha_anterior = linha
                    continue

                # Verifica se é uma ação (ticker com 4-6 caracteres + número)
                ticker_match = re.match(r'^([A-Z]{4}\d{1,2})\s', linha_upper)
                if ticker_match:
                    ticker = ticker_match.group(1)
                    valores = padrao_valor.findall(linha)

                    if valores:
                        # Pega o último valor (geralmente é a posição)
                        valor_str = valores[-1].replace('.', '').replace(',', '.')
                        try:
                            valor = float(valor_str)
                            if valor >= 50 and ticker not in produtos_vistos:
                                produtos_vistos.add(ticker)
                                produtos.append({
                                    'tipo': 'Renda Variável',
                                    'nome': ticker,
                                    'valor': valor
                                })
                        except:
                            pass
                    linha_anterior = linha
                    continue

                # Verifica se é Renda Fixa
                is_rf = any(padrao in linha_upper for padrao in padroes_rf)
                if is_rf:
                    valores = padrao_valor.findall(linha)
                    if valores:
                        # Pega o último valor (geralmente é a posição)
                        valor_str = valores[-1].replace('.', '').replace(',', '.')
                        try:
                            valor = float(valor_str)
                            if valor >= 50:
                                # Nome do produto: limpa valores e datas
                                nome = linha.strip()
                                nome = re.sub(r'R?\$?\s*[\d.,]+', '', nome)
                                nome = re.sub(r'\d{2}/\d{2}/\d{4}', '', nome)
                                nome = re.sub(r'\d+[,.]?\d*\s*%', '', nome)
                                nome = re.sub(r'\s{2,}', ' ', nome).strip()[:100]

                                if len(nome) >= 5:
                                    chave = f"{nome[:30]}_{int(valor)}"
                                    if chave not in produtos_vistos:
                                        produtos_vistos.add(chave)
                                        produtos.append({
                                            'tipo': 'Renda Fixa',
                                            'nome': nome,
                                            'valor': valor
                                        })
                        except:
                            pass

                linha_anterior = linha

            # Calcular totais
            total_rf = sum(p['valor'] for p in produtos if p['tipo'] == 'Renda Fixa')
            total_rv = sum(p['valor'] for p in produtos if p['tipo'] == 'Renda Variável')
            total = total_rf + total_rv

            resultado = {
                'produtos': produtos,
                'resumo': {
                    'totalRendaFixa': total_rf,
                    'totalRendaVariavel': total_rv,
                    'total': total,
                    'percentualRF': round((total_rf / total * 100) if total > 0 else 0, 2),
                    'percentualRV': round((total_rv / total * 100) if total > 0 else 0, 2)
                }
            }

            return resultado

    except Exception as e:
        print(f"Erro ao processar PDF: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Aceita caminho do PDF como argumento ou usa o padrão
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = r'C:\Users\blank\Downloads\Posicao Detalhada - 3924287.pdf'

    resultado = extrair_posicao_detalhada(pdf_path)

    if resultado:
        print("\n=== RESUMO DA CARTEIRA ===")
        print(f"Total: R$ {resultado['resumo']['total']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        print(f"Renda Fixa: R$ {resultado['resumo']['totalRendaFixa']:,.2f} ({resultado['resumo']['percentualRF']}%)".replace(',', 'X').replace('.', ',').replace('X', '.'))
        print(f"Renda Variável: R$ {resultado['resumo']['totalRendaVariavel']:,.2f} ({resultado['resumo']['percentualRV']}%)".replace(',', 'X').replace('.', ',').replace('X', '.'))

        print(f"\n=== PRODUTOS ENCONTRADOS ({len(resultado['produtos'])}) ===")

        # Agrupa por tipo
        rf_produtos = [p for p in resultado['produtos'] if p['tipo'] == 'Renda Fixa']
        rv_produtos = [p for p in resultado['produtos'] if p['tipo'] == 'Renda Variável']

        if rf_produtos:
            print("\n--- RENDA FIXA ---")
            for i, p in enumerate(rf_produtos, 1):
                print(f"{i}. {p['nome']} - R$ {p['valor']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))

        if rv_produtos:
            print("\n--- RENDA VARIÁVEL ---")
            for i, p in enumerate(rv_produtos, 1):
                print(f"{i}. {p['nome']} - R$ {p['valor']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))

        # Salvar JSON
        with open('carteira-extraida.json', 'w', encoding='utf-8') as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)

        print("\nDados salvos em carteira-extraida.json")

