import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from datetime import datetime

WINE = colors.HexColor("#7A1F2B")
LIGHT_GREY = colors.HexColor("#F2F2F2")
MEDIUM_GREY = colors.HexColor("#E0E0E0")
YELLOW = colors.HexColor("#FFE600")
BLACK = colors.black
WHITE = colors.white

# Caminho do logo
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")

def gerar_pdfs(df, tipo_envio, mes_referencia, link_form):
    """
    Gera PDFs agrupados por beneficiário.
    Salva os PDFs em uploads/{tipo_envio}/
    """
    tipo_folder = tipo_envio.lower()
    pasta_destino = os.path.join(BASE_DIR, "uploads", tipo_folder)
    os.makedirs(pasta_destino, exist_ok=True)
    
    pdfs_gerados = []
    erros = []
    
    # Agrupar por corretor
    grouped = df.groupby('BENEFICIARIO')
    
    for beneficiario, group in grouped:
        try:
            # Limpar nome do arquivo
            nome_arquivo = f"{str(beneficiario).replace('/', '-').replace(':', '')}.pdf"
            caminho_pdf = os.path.join(pasta_destino, nome_arquivo)
            
            # Caminho relativo para o banco (ex: premiação - metas/Arquivo.pdf)
            caminho_relativo = f"{tipo_folder}/{nome_arquivo}"
            
            c = canvas.Canvas(caminho_pdf, pagesize=landscape(A4))
            width, height = landscape(A4)

            def draw_header():
                c.setFillColor(WINE)
                c.rect(0, height - 95, width, 95, fill=1)

                c.setFillColor(WHITE)
                c.setFont("Helvetica-Bold", 17)
                c.drawString(40, height - 38, f"Relatório - {tipo_envio}")

                c.setFont("Helvetica-Bold", 12)
                c.drawString(40, height - 58, f"Beneficiário: {beneficiario}")

                c.setFont("Helvetica-Bold", 10)
                c.drawString(40, height - 74, f"Mês de Referência: {mes_referencia}")

                if os.path.exists(LOGO_PATH):
                    try:
                        logo_height = 78
                        logo_width = 150
                        logo_x = width - logo_width - 40
                        logo_y = height - logo_height - 8
                        c.drawImage(LOGO_PATH, logo_x, logo_y, width=logo_width, height=logo_height, preserveAspectRatio=True, mask='auto')
                    except Exception as e:
                        print(f"Erro ao desenhar logo: {e}")

            draw_header()

            y_position = height - 145
            x_start = 40

            headers = ["Empreendimento", "Unidade", "Valor Total"]
            col_widths = [250, 330, 150]

            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(MEDIUM_GREY)
            c.setStrokeColor(BLACK)
            c.setLineWidth(1)
            c.rect(x_start, y_position - 25, sum(col_widths), 30, fill=1, stroke=1)

            x = x_start
            for i, header in enumerate(headers):
                c.setFillColor(BLACK)
                c.drawCentredString(x + col_widths[i] / 2, y_position - 15, header)
                x += col_widths[i]

            y_position -= 30
            c.setFont("Helvetica", 10)

            zebra = False

            def draw_table_headers():
                nonlocal y_position
                c.setFont("Helvetica-Bold", 10)
                c.setFillColor(MEDIUM_GREY)
                c.setStrokeColor(BLACK)
                c.setLineWidth(1)
                c.rect(x_start, y_position - 25, sum(col_widths), 30, fill=1, stroke=1)
                x = x_start
                for i, header in enumerate(headers):
                    c.setFillColor(BLACK)
                    c.drawCentredString(x + col_widths[i] / 2, y_position - 15, header)
                    x += col_widths[i]
                y_position -= 30
                c.setFont("Helvetica", 10)

            def draw_row(emp_text, unidade_text, valor_str, is_total_row):
                nonlocal y_position, zebra
                if y_position < 140:
                    c.showPage()
                    draw_header()
                    y_position = height - 145
                    draw_table_headers()

                if is_total_row:
                    c.setFillColor(YELLOW)
                else:
                    c.setFillColor(LIGHT_GREY if zebra else WHITE)

                c.rect(x_start, y_position - 22, sum(col_widths), 28, fill=1, stroke=0)

                values = [emp_text, unidade_text, valor_str]
                x = x_start
                c.setFont("Helvetica-Bold" if is_total_row else "Helvetica", 10)
                for i, value in enumerate(values):
                    c.setFillColor(BLACK)
                    c.drawCentredString(x + col_widths[i] / 2, y_position - 14, str(value)[:60])
                    x += col_widths[i]

                c.setStrokeColor(BLACK)
                c.setLineWidth(0.8)
                c.rect(x_start, y_position - 22, sum(col_widths), 28, fill=0)

                x_line = x_start
                for w in col_widths[:-1]:
                    x_line += w
                    c.line(x_line, y_position - 22, x_line, y_position + 6)

                y_position -= 28
                if not is_total_row:
                    zebra = not zebra

            def fmt_valor(v):
                try:
                    return float(v)
                except Exception:
                    return 0.0

            def fmt_brl(v):
                return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            # Filtrar linhas TOTAL vindas da planilha (serão recalculadas por empreendimento)
            data_rows = group[group['UNIDADE'].str.strip().str.upper() != 'TOTAL'].copy()

            # Pré-calcular total por empreendimento
            totais_emp = (
                data_rows.groupby('EMPREENDIMENTO')['VALOR TOTAL']
                .apply(lambda s: sum(fmt_valor(v) for v in s))
                .to_dict()
            )

            current_emp = None
            for _, row in data_rows.iterrows():
                emp = str(row['EMPREENDIMENTO'])

                # Ao trocar de empreendimento, desenha linha amarela de total do anterior
                if current_emp is not None and emp != current_emp:
                    draw_row(current_emp, "TOTAL", fmt_brl(totais_emp[current_emp]), True)

                current_emp = emp
                draw_row(emp, str(row['UNIDADE']), fmt_brl(fmt_valor(row['VALOR TOTAL'])), False)

            # Linha amarela do último empreendimento
            if current_emp is not None:
                draw_row(current_emp, "TOTAL", fmt_brl(totais_emp[current_emp]), True)

            # Botão Acessar Formulário
            if link_form:
                button_width = 160
                button_height = 32
                button_x = (width - button_width) / 2
                button_y = y_position - 45

                c.setFillColor(WINE)
                c.roundRect(button_x, button_y, button_width, button_height, 10, fill=1)

                c.setFillColor(WHITE)
                c.setFont("Helvetica-Bold", 10)
                c.drawCentredString(
                    button_x + button_width / 2,
                    button_y + 11,
                    "Acessar Formulário"
                )

                c.linkURL(
                    link_form,
                    (button_x, button_y, button_x + button_width, button_y + button_height),
                    relative=0
                )

            c.showPage()
            c.save()
            
            pdfs_gerados.append({
                'corretor': beneficiario,
                'caminho': caminho_pdf,
                'caminho_relativo': caminho_relativo
            })
            
        except Exception as e:
            erros.append(f"Erro ao gerar PDF para {beneficiario}: {str(e)}")

    return {
        'sucesso': len(erros) == 0,
        'pdfs': pdfs_gerados,
        'erros': erros
    }
