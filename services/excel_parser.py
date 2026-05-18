import pandas as pd
import os

def processar_planilha_base(caminho_arquivo, tipo_envio):
    """
    Processa a planilha base de imobiliárias lendo a Tabela Dinâmica.
    Retorna dicionário com status, corretores, empreendimentos e dataframe processado.
    """
    try:
        with pd.ExcelFile(caminho_arquivo) as excel_file:
            abas = excel_file.sheet_names
            
            # 1. Pré-detecção Universal de Tabela Plana (Flat Table)
            # Tenta encontrar a melhor aba disponível
            aba_selecionada = None
            aba_exata = f"Fechamento {tipo_envio}"
            for aba in abas:
                if aba.lower().strip() == aba_exata.lower():
                    aba_selecionada = aba
                    break
            
            if not aba_selecionada:
                for aba in abas:
                    if 'fechamento' in aba.lower() and tipo_envio.lower() in aba.lower():
                        aba_selecionada = aba
                        break
                        
            if not aba_selecionada:
                for aba in abas:
                    if tipo_envio.lower() in aba.lower():
                        aba_selecionada = aba
                        break

            # Fallbacks adicionais de abas comuns caso não encontre por nome
            if not aba_selecionada:
                for fallback_name in ['DADOS', 'PLANILHA1', 'PLANILHA2']:
                    for aba in abas:
                        if aba.upper().strip() == fallback_name:
                            aba_selecionada = aba
                            break
                    if aba_selecionada:
                        break
            
            if not aba_selecionada:
                aba_selecionada = abas[0]  # Fallback final: primeira aba

            # Analisar as colunas da aba selecionada
            df_temp = pd.read_excel(excel_file, sheet_name=aba_selecionada, nrows=2)
            cols_originais = list(df_temp.columns)
            cols_normalized = [str(c).strip().upper() for c in cols_originais]
            
            col_benef = None
            col_emp = None
            col_uni = None
            col_val = None
            
            for orig, norm in zip(cols_originais, cols_normalized):
                if 'BENEFIC' in norm or 'NOME' in norm or 'CORRETOR' in norm:
                    col_benef = orig
                elif 'EMPREEND' in norm or 'PROJETO' in norm:
                    col_emp = orig
                elif 'UNIDADE' in norm or 'APTO' in norm:
                    col_uni = orig
                elif 'VALOR' in norm or 'PREMIO' in norm or 'PRMIO' in norm:
                    col_val = orig

            is_flat = col_benef is not None and col_val is not None

            # Se for detectada como Tabela Plana (Flat Table), processamos de forma direta e otimizada!
            if is_flat:
                df_raw = pd.read_excel(excel_file, sheet_name=aba_selecionada)
                
                # Remover beneficiário nulo
                df_raw = df_raw.dropna(subset=[col_benef])
                df_raw = df_raw[~df_raw[col_benef].astype(str).str.strip().str.lower().isin(['nan', '', 'none', 'total', 'subtotal'])]
                
                # Converter valor para numérico e filtrar positivos
                df_raw[col_val] = pd.to_numeric(df_raw[col_val], errors='coerce').fillna(0)
                df_raw = df_raw[df_raw[col_val] > 0].reset_index(drop=True)

                if df_raw.empty:
                    raise ValueError(f"Nenhum dado de valor positivo encontrado na aba plana '{aba_selecionada}'.")

                df_flat = pd.DataFrame()
                df_flat['BENEFICIARIO']   = df_raw[col_benef].astype(str).str.strip()
                df_flat['EMPREENDIMENTO'] = df_raw[col_emp].astype(str).str.strip() if col_emp else 'GERAL'
                df_flat['UNIDADE']        = df_raw[col_uni].astype(str).str.strip() if col_uni else '-'
                df_flat['VALOR TOTAL']    = df_raw[col_val]
                
                corretores_nomes = [str(x).strip() for x in df_flat['BENEFICIARIO'].dropna().unique() if str(x).strip()]
                
                empreendimentos_por_corretor = {}
                for nome in corretores_nomes:
                    emps = df_flat[df_flat['BENEFICIARIO'] == nome]['EMPREENDIMENTO'].dropna().unique().tolist()
                    empreendimentos_por_corretor[nome] = ", ".join(str(e).strip() for e in emps if str(e).strip() != "nan")
                
                return {
                    'sucesso': True,
                    'dataframe': df_flat,
                    'corretores': corretores_nomes,
                    'empreendimentos_por_corretor': empreendimentos_por_corretor,
                    'aba_lida': aba_selecionada
                }
                
            # Extrair Imobiliárias e Empreendimentos das outras abas para mapeamento (Dicionário global)
            imobs_conhecidas = set()
            emps_conhecidos = set()
            for aba in abas:
                if aba == aba_selecionada: continue
                try:
                    df_temp = pd.read_excel(excel_file, sheet_name=aba, nrows=5000)
                    # Tenta achar colunas que parecem ser Imobiliaria e Empreendimento
                    for col in df_temp.columns:
                        col_str = str(col).lower()
                        if 'imobili' in col_str and 'final' in col_str:
                            valores = [str(x).strip() for x in df_temp[col].dropna().unique() if str(x).strip() not in ['nan', 'None', '0', '0.0'] and not str(x).strip().replace('.','',1).isdigit()]
                            imobs_conhecidas.update(valores)
                        elif 'imobili' in col_str or 'corretor' in col_str or 'parceiro' in col_str:
                            valores = [str(x).strip() for x in df_temp[col].dropna().unique() if str(x).strip() not in ['nan', 'None', '0', '0.0'] and not str(x).strip().replace('.','',1).isdigit()]
                            imobs_conhecidas.update(valores)
                        elif 'empreend' in col_str:
                            valores = [str(x).strip() for x in df_temp[col].dropna().unique() if str(x).strip() not in ['nan', 'None', '0', '0.0'] and not str(x).strip().replace('.','',1).isdigit()]
                            emps_conhecidos.update(valores)
                except Exception:
                    pass
                    
            # Lendo a Tabela Dinâmica sem cabeçalho para não perder dados
            df_pivot = pd.read_excel(excel_file, sheet_name=aba_selecionada, header=None)
            
            # Encontrar as colunas de dados (Onde está o Rótulo, Quantidade e Valor)
            col_rotulo = 0
            col_quant = -1
            col_valor = -1
            
            # Procura os índices das colunas
            for idx, row in df_pivot.iterrows():
                linha_str = [str(x).lower() for x in row.values]
                for i, val in enumerate(linha_str):
                    if 'quant' in val: col_quant = i
                    elif 'valor' in val and 'comis' in val: col_valor = i
                    elif 'valor' in val and col_valor == -1: col_valor = i
                    
                if col_quant != -1 and col_valor != -1:
                    break
                    
            if col_valor == -1:
                raise ValueError("Não foi possível identificar a coluna de 'Valor' na Tabela Dinâmica.")
                
            flat_data = []
            current_imob = None
            current_emp = None
            
            # Heurísticas de região para ignorar
            regioes = ['ALTO TIETE', 'GRANDE CAMPINAS', 'GRANDE SÃO PAULO', 'VALE DO PARAIBA', 'NORDESTE', 'SUL', 'NORTE']
            
            for idx, row in df_pivot.iterrows():
                val_raw = row[col_rotulo]
                if pd.isna(val_raw): continue
                
                val = str(val_raw).strip()
                if not val or val.lower().startswith('total') or val == 'nan':
                    continue
                    
                valor_num = row[col_valor]
                # Se já for numérico (float ou int), usamos direto
                if isinstance(valor_num, (int, float)):
                    valor_float = float(valor_num)
                else:
                    try:
                        valor_str = str(valor_num).strip().upper()
                        if valor_str == 'NAN' or valor_str == 'NONE' or not valor_str:
                            continue
                        # Se for string, removemos R$ e pontos de milhar, trocamos vírgula decimal por ponto
                        valor_float = float(valor_str.replace('R$', '').replace('.', '').replace(',', '.').strip())
                    except (ValueError, TypeError):
                        continue
                    
                val_upper = val.upper()
                
                # 1. Ignorar Regiões
                is_regiao = any(r in val_upper for r in regioes)
                if is_regiao and val not in imobs_conhecidas:
                    continue
                    
                # 2. Identificar o Nível
                if val in imobs_conhecidas or 'IMOVEIS' in val_upper or 'LTDA' in val_upper or 'CONSULTORIA' in val_upper or 'NEGOCIOS' in val_upper or 'CORRETOR' in val_upper or 'AUTONOMO' in val_upper or 'PARCEIRO' in val_upper or 'ASSOCIADO' in val_upper:
                    current_imob = val
                    current_emp = None # Reseta o empreendimento ao mudar a imobiliária
                elif val in emps_conhecidos or val_upper.startswith('SOU ') or val_upper.startswith('RESIDENCIAL ') or val_upper.startswith('SAFIRA') or val_upper.startswith('AMETISTA'):
                    current_emp = val
                else:
                    # Se não é Imob nem Emp, assumimos que é uma Unidade (nível mais baixo)
                    if current_imob and current_emp:
                        flat_data.append({
                            'BENEFICIARIO': current_imob,
                            'EMPREENDIMENTO': current_emp,
                            'UNIDADE': val,
                            'VALOR TOTAL': valor_float
                        })

            df_flat = pd.DataFrame(flat_data)
            
            if df_flat.empty:
                raise ValueError("A leitura da Tabela Dinâmica não encontrou dados válidos. Verifique o formato da aba.")
                
            # Obter lista única de corretores
            corretores_df = df_flat[['BENEFICIARIO']].drop_duplicates()
            corretores_nomes = corretores_df['BENEFICIARIO'].tolist()
            
            # Obter os empreendimentos de cada corretor
            empreendimentos_por_corretor = {}
            for nome in corretores_nomes:
                emps = df_flat[df_flat['BENEFICIARIO'] == nome]['EMPREENDIMENTO'].dropna().unique().tolist()
                empreendimentos_por_corretor[nome] = ", ".join(str(e).strip() for e in emps if str(e).strip() != "nan")
            
            return {
                'sucesso': True,
                'dataframe': df_flat,
                'corretores': corretores_nomes,
                'empreendimentos_por_corretor': empreendimentos_por_corretor,
                'aba_lida': aba_selecionada
            }
        
    except Exception as e:
        return {
            'sucesso': False,
            'erro': str(e)
        }
