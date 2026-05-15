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
            
            # 1. Lógica para House e Staff
            if tipo_envio in ['House', 'Staff']:

                # --- ETAPA 1: Achar aba com coluna "Cargo" real nos dados ---
                aba_com_cargo = None
                aba_fechamento = None
                aba_fallback = None

                for aba in abas:
                    aba_l = aba.lower()
                    if 'fechamento comercial' in aba_l:
                        aba_fechamento = aba
                    if 'comissoes_parti' in aba_l:
                        aba_fallback = aba
                    # Verificar se essa aba tem "Cargo" como coluna de dados real
                    try:
                        df_test = pd.read_excel(excel_file, sheet_name=aba, nrows=15, header=None)
                        for i, row in df_test.iterrows():
                            row_vals = [str(v).lower() for v in row.values]
                            if any('cargo' in v for v in row_vals) and any('benefic' in v for v in row_vals):
                                df_cols_check = pd.read_excel(excel_file, sheet_name=aba, skiprows=i, nrows=2)
                                if any('cargo' in str(c).lower() for c in df_cols_check.columns):
                                    aba_com_cargo = aba
                                break
                    except Exception:
                        pass
                    if aba_com_cargo:
                        break

                # Preferência: aba com cargo > fechamento > fallback
                aba_dados = aba_com_cargo or aba_fechamento or aba_fallback

                if not aba_dados:
                    raise ValueError("Nenhuma aba com dados de comissão encontrada.")

                # --- ETAPA 2: Encontrar linha de cabeçalho real ---
                df_header_search = pd.read_excel(excel_file, sheet_name=aba_dados, header=None, nrows=20)
                header_idx = 0
                for idx, row in df_header_search.iterrows():
                    row_str = [str(x).lower() for x in row.values]
                    if any('benefic' in s for s in row_str):
                        header_idx = idx
                        break

                df_raw = pd.read_excel(excel_file, sheet_name=aba_dados, skiprows=header_idx)

                # --- ETAPA 3: Mapeamento flexível de colunas ---
                col_map_raw = {}
                for c in df_raw.columns:
                    c_l = str(c).lower()
                    if 'benefic' in c_l and 'beneficiario' not in col_map_raw:
                        col_map_raw['beneficiario'] = c
                    elif 'cargo' in c_l and 'cargo' not in col_map_raw:
                        col_map_raw['cargo'] = c
                    elif 'empreend' in c_l and 'empreendimento' not in col_map_raw:
                        col_map_raw['empreendimento'] = c
                    elif ('unidade' in c_l or 'identif' in c_l) and 'unidade' not in col_map_raw:
                        col_map_raw['unidade'] = c
                    elif ('receber' in c_l or 'pagar' in c_l or 'comiss' in c_l) and 'valor' not in col_map_raw:
                        col_map_raw['valor'] = c
                    elif 'valor' in c_l and 'valor' not in col_map_raw:
                        col_map_raw['valor'] = c

                if 'beneficiario' not in col_map_raw:
                    raise ValueError(f"Coluna 'Beneficiário' não encontrada na aba '{aba_dados}'.")

                # --- ETAPA 4: Tratamento de Tabela Dinâmica (FFILL + remover Totais) ---
                cols_to_fill = [col_map_raw['beneficiario']]
                if 'empreendimento' in col_map_raw:
                    cols_to_fill.append(col_map_raw['empreendimento'])
                df_raw[cols_to_fill] = df_raw[cols_to_fill].ffill()

                # Remover linhas de Total do beneficiário E do empreendimento
                df_raw = df_raw[~df_raw[col_map_raw['beneficiario']].astype(str).str.contains('Total', case=False, na=False)]
                if 'empreendimento' in col_map_raw:
                    df_raw = df_raw[~df_raw[col_map_raw['empreendimento']].astype(str).str.contains('Total', case=False, na=False)]

                # --- ETAPA 5: Filtro por Cargo ---
                if 'cargo' in col_map_raw:
                    df_raw[col_map_raw['cargo']] = df_raw[col_map_raw['cargo']].astype(str).str.strip()
                    if tipo_envio == 'House':
                        df_filtered = df_raw[df_raw[col_map_raw['cargo']].str.lower() == 'corretor'].copy()
                    else:  # Staff
                        excluir = ['corretor', 'parceiro', 'nan', 'none']
                        df_filtered = df_raw[~df_raw[col_map_raw['cargo']].str.lower().isin(excluir)].copy()
                else:
                    raise ValueError(
                        f"Coluna 'Cargo' não encontrada como coluna de dados na aba '{aba_dados}'. "
                        f"O arquivo precisa ter 'Cargo' como coluna (não apenas filtro de Tabela Dinâmica)."
                    )

                # --- ETAPA 6: Filtro de valor ---
                col_benef = col_map_raw['beneficiario']
                col_emp   = col_map_raw.get('empreendimento')
                col_uni   = col_map_raw.get('unidade')
                col_val   = col_map_raw.get('valor')

                if col_val:
                    df_filtered.loc[:, col_val] = pd.to_numeric(df_filtered[col_val], errors='coerce').fillna(0)
                    df_filtered = df_filtered[df_filtered[col_val] > 0]

                if df_filtered.empty:
                    raise ValueError(f"Nenhum dado para '{tipo_envio}' após filtro de Cargo e Valor.")

                # --- ETAPA 7: DataFrame final ---
                df_flat = pd.DataFrame(index=df_filtered.index)
                df_flat['BENEFICIARIO']   = df_filtered[col_benef].astype(str).str.strip()
                df_flat['EMPREENDIMENTO'] = df_filtered[col_emp].astype(str).str.strip() if col_emp else 'GERAL'
                df_flat['UNIDADE']        = df_filtered[col_uni].astype(str).str.strip() if col_uni else '-'
                df_flat['VALOR TOTAL']    = pd.to_numeric(df_filtered[col_val], errors='coerce').fillna(0) if col_val else 0

                df_flat = df_flat[~df_flat['BENEFICIARIO'].str.lower().isin(['nan', '', 'none'])]
                df_flat = df_flat[~df_flat['EMPREENDIMENTO'].str.lower().isin(['nan', '', 'none'])]
                df_flat = df_flat[df_flat['VALOR TOTAL'] > 0].reset_index(drop=True)
                
                # Obter lista única de corretores
                corretores_nomes = [str(x).strip() for x in df_flat['BENEFICIARIO'].dropna().unique() if str(x).strip()]
                
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
                    'aba_lida': aba_dados
                }

            # 2. Lógica para Prêmio (Padrão Flat ou Pivot)
            if tipo_envio in ['Prêmio', 'Premiação - Metas']:
                aba_selecionada = None
                # Primeiro tenta o padrão Flat (colunas diretas)
                for aba in abas:
                    df_temp = pd.read_excel(excel_file, sheet_name=aba, nrows=5)
                    cols = [str(c).upper().strip() for c in df_temp.columns]
                    tem_benef = any('BENEFIC' in c or 'NOME' in c or 'CORRETOR' in c for c in cols)
                    tem_valor = any('VALOR' in c or 'PREMIO' in c or 'PRMIO' in c for c in cols)
                    
                    if tem_benef and tem_valor:
                        aba_selecionada = aba
                        break
                
                if aba_selecionada:
                    df_flat_raw = pd.read_excel(excel_file, sheet_name=aba_selecionada)
                    col_map = {}
                    for c in df_flat_raw.columns:
                        c_up = str(c).upper().strip()
                        if 'BENEFIC' in c_up or 'NOME' in c_up or 'CORRETOR' in c_up: col_map['BENEFICIARIO'] = c
                        elif 'EMPREEND' in c_up or 'PROJETO' in c_up: col_map['EMPREENDIMENTO'] = c
                        elif 'UNIDADE' in c_up or 'IDENTIF' in c_up: col_map['UNIDADE'] = c
                        elif 'VALOR' in c_up or 'PREMIO' in c_up or 'PRMIO' in c_up: col_map['VALOR TOTAL'] = c
                    
                    if 'BENEFICIARIO' in col_map and 'VALOR TOTAL' in col_map:
                        df_flat_raw = df_flat_raw.dropna(subset=[col_map['BENEFICIARIO'], col_map['VALOR TOTAL']])
                        df_flat_raw[col_map['VALOR TOTAL']] = pd.to_numeric(df_flat_raw[col_map['VALOR TOTAL']], errors='coerce').fillna(0)
                        df_flat_raw = df_flat_raw[df_flat_raw[col_map['VALOR TOTAL']] > 0]
                        
                        df_flat = df_flat_raw.rename(columns={
                            col_map['BENEFICIARIO']: 'BENEFICIARIO',
                            col_map.get('EMPREENDIMENTO', 'EMPREENDIMENTO'): 'EMPREENDIMENTO',
                            col_map.get('UNIDADE', 'UNIDADE'): 'UNIDADE',
                            col_map['VALOR TOTAL']: 'VALOR TOTAL'
                        })
                        if 'EMPREENDIMENTO' not in df_flat.columns: df_flat['EMPREENDIMENTO'] = 'GERAL'
                        if 'UNIDADE' not in df_flat.columns: df_flat['UNIDADE'] = '-'
                        
                        df_flat = df_flat[['BENEFICIARIO', 'EMPREENDIMENTO', 'UNIDADE', 'VALOR TOTAL']]
                        corretores_nomes = [str(x).strip() for x in df_flat['BENEFICIARIO'].dropna().unique() if str(x).strip()]
                        empreendimentos_por_corretor = {}
                        for nome in corretores_nomes:
                            emps_list = df_flat[df_flat['BENEFICIARIO'] == nome]['EMPREENDIMENTO'].dropna().unique().tolist()
                            empreendimentos_por_corretor[nome] = ", ".join(str(e).strip() for e in emps_list if str(e).strip() != "nan")
                        
                        return {
                            'sucesso': True,
                            'dataframe': df_flat,
                            'corretores': corretores_nomes,
                            'empreendimentos_por_corretor': empreendimentos_por_corretor,
                            'aba_lida': aba_selecionada
                        }
            
            aba_selecionada = None
            # Tenta achar correspondência exata primeiro
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
                    
            if not aba_selecionada:
                raise ValueError(f"Aba para {tipo_envio} não encontrada. Abas disponíveis: {', '.join(abas)}")
                
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
