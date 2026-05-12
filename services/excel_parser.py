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
            
            # 1. Lógica para House e Staff (Via Aba de Dados Brutos)
            if tipo_envio in ['House', 'Staff']:
                aba_dados = None
                for aba in abas:
                    if 'comissoes_parti' in aba.lower():
                        aba_dados = aba
                        break
                
                if not aba_dados:
                    raise ValueError("Aba de dados brutos (relatorios_comissoes_parti_CV) não encontrada.")
                
                df_raw = pd.read_excel(excel_file, sheet_name=aba_dados)
                
                # Garantir que as colunas existem
                colunas_requeridas = ['Cargo', 'Beneficiário', 'Empreendimento Final', 'Identificador', 'Valor a Pagar']
                for col in colunas_requeridas:
                    if col not in df_raw.columns:
                        raise ValueError(f"Coluna '{col}' não encontrada na aba {aba_dados}.")
                
                # Filtro de valor zerado ou nulo
                df_raw = df_raw[df_raw['Valor a Pagar'].notna()]
                df_raw['Valor a Pagar'] = pd.to_numeric(df_raw['Valor a Pagar'], errors='coerce').fillna(0)
                df_raw = df_raw[df_raw['Valor a Pagar'] != 0]
                
                if tipo_envio == 'House':
                    df_filtered = df_raw[df_raw['Cargo'].astype(str).str.strip() == 'Corretor']
                else: # Staff
                    df_filtered = df_raw[~df_raw['Cargo'].astype(str).str.strip().isin(['Corretor', 'Parceiro'])]
                
                if df_filtered.empty:
                    raise ValueError(f"Nenhum dado encontrado para a categoria {tipo_envio} após os filtros de Cargo e Valor.")
                
                # Mapear para o formato flat
                df_flat = df_filtered.rename(columns={
                    'Beneficiário': 'BENEFICIARIO',
                    'Empreendimento Final': 'EMPREENDIMENTO',
                    'Identificador': 'UNIDADE',
                    'Valor a Pagar': 'VALOR TOTAL'
                })[['BENEFICIARIO', 'EMPREENDIMENTO', 'UNIDADE', 'VALOR TOTAL']]
                
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
            if tipo_envio == 'Prêmio':
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
