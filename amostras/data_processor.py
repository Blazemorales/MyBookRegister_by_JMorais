import json
import math
import os
import numpy as np
from scipy.stats import norm


class DataProcessor:
    """Processa dados brutos de amostras e gera dados tratados."""
    
    def __init__(self):
        self.datasets = []
        self.dados_tratados = []
        
        # Define o diretório onde o arquivo .py atual está localizado
        self.diretorio_script = os.path.dirname(os.path.abspath(__file__))
        
        # Define a raiz do projeto (um nível acima da pasta 'amostras')
        self.raiz_projeto = os.path.dirname(self.diretorio_script)
        
        # Nome de arquivo padrão
        self.nome_arquivo_padrao = 'dados_producao_total.json'

    def carregar_dados_brutos(self, nome_arquivo=None):
        """
        Carrega dados brutos do arquivo JSON. 
        Se nome_arquivo não for fornecido, usa o padrão definido no __init__.
        """
        # Se não enviou nome no argumento, usa o self.nome_arquivo_padrao
        arquivo_para_abrir = self.nome_arquivo_padrao
        
        # Monta o caminho: diretorio_do_script/banco_de_dados_amostras/arquivo.json
        caminho_completo = os.path.join(
            self.diretorio_script, 
            'banco_de_dados_amostras', 
            arquivo_para_abrir
        )
        
        try:
            with open(caminho_completo, 'r', encoding='utf-8') as f:
                conteudo = json.load(f)
                # Garante que datasets seja sempre uma lista
                self.datasets = conteudo if isinstance(conteudo, list) else [conteudo]
            
            print(f"✓ Dados brutos carregados com sucesso: {arquivo_para_abrir}")
            return True
            
        except FileNotFoundError:
            print(f"✗ Erro: O arquivo '{arquivo_para_abrir}' não foi encontrado.")
            print(f"   Caminho tentado: {caminho_completo}")
            return False
        except json.JSONDecodeError:
            print(f"✗ Erro: O arquivo '{arquivo_para_abrir}' não é um JSON válido.")
            return False
        except Exception as e:
            print(f"✗ Erro inesperado ao carregar {arquivo_para_abrir}: {e}")
            return False
    
    def processar_tipo_xr(self, ds):
        """Processa dados para Carta XR (Médias e Amplitudes)."""
        measurements = ds.get("measurements", {})
        if not measurements:
            return None
        
        lse = ds.get("Limite sup. Esp", 0)
        lie = ds.get("Limite inf. Esp", 0)
        
        todas_as_medias = []
        amplitudes = []
        todos_os_valores = []
        estatisticas_por_amostra = []
        
        for id_amostra, valores in measurements.items():
            if valores:
                n_amostra = len(valores)
                media_amostra = np.mean(valores)
                amplitude_amostra = max(valores) - min(valores)
                
                soma_quad = sum((x - media_amostra) ** 2 for x in valores)
                dp_amostra = np.sqrt(soma_quad / n_amostra)
                
                estatisticas_por_amostra.append({
                    "amostra": str(id_amostra),
                    "media": float(media_amostra),
                    "dp": float(dp_amostra),
                    "amplitude": float(amplitude_amostra),
                    "n": n_amostra,
                    "valores": valores
                })
                
                todas_as_medias.append(media_amostra)
                amplitudes.append(amplitude_amostra)
                todos_os_valores.extend(valores)
        
        if not todos_os_valores:
            return None
        
        # Cálculos globais
        x_double_bar = np.mean(todas_as_medias)
        r_bar = np.mean(amplitudes)
        sigma = np.std(todos_os_valores, ddof=0)
        
        # Determinar d2 baseado em n
        n_amostra = len(valores)
        d2_values = {
            2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326,
            6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078
        }
        d2 = d2_values.get(n_amostra, n_amostra / (n_amostra - 0.8) * math.sqrt(math.log(n_amostra)))
        
        lsc_r = r_bar * (1 + 3 * (0.864 / d2)) if d2 != 0 else 0
        lic_r = max(0, r_bar * (1 - 3 * (0.864 / d2))) if d2 != 0 else 0
        
        return {
            "chart": "XR",
            "lse": float(lse),
            "lie": float(lie),
            "x_double_bar": float(x_double_bar),
            "r_bar": float(r_bar),
            "sigma": float(sigma),
            "lsc_x": float(x_double_bar + 3 * sigma),
            "lic_x": float(x_double_bar - 3 * sigma),
            "lsc_r": float(lsc_r),
            "lic_r": float(lic_r),
            "n_amostra": n_amostra,
            "estatisticas_por_amostra": estatisticas_por_amostra
        }
    
    def processar_tipo_p(self, ds):
        """Processa dados para Carta P (Proporção de Defeituosos)."""
        measurements = ds.get("measurements", {})
        if not measurements:
            return None

        # Tamanho da amostra (número de unidades por subamostra)
        N = ds.get("n_amostra") or ds.get("N")
        if not N:
            # Não há informação de tamanho de amostra
            return None

        # Extrair defeitos por amostra (cada entrada pode ser lista ou número)
        defeitos = []
        for k, v in measurements.items():
            if isinstance(v, list) and len(v) > 0:
                defeitos.append(int(v[0]))
            elif isinstance(v, (int, float)):
                defeitos.append(int(v))

        if not defeitos:
            return None

        m = len(defeitos)
        proporcoes = [d / N for d in defeitos]
        P_bar = float(np.mean(proporcoes))
        total_defeitos = sum(defeitos)
        P_overall = total_defeitos / (N * m)

        # Desvio padrão para p-chart (assumindo N constante)
        desvio_padrao_p = float(np.sqrt((P_bar * (1 - P_bar)) / N)) if N > 0 else 0.0

        lsc_P = min(1.0, P_bar + 3 * desvio_padrao_p)
        lic_P = max(0.0, P_bar - 3 * desvio_padrao_p)

        return {
            "chart": "P",
            "P": float(P_overall),
            "P_bar": float(P_bar),
            "total_defeitos": int(total_defeitos),
            "N": int(N),
            "desvio_padrao_p": float(desvio_padrao_p),
            "lsc_P": float(lsc_P),
            "lic_P": float(lic_P),
            "proporcoes": [float(p) for p in proporcoes]
        }
    
    def processar_tipo_u(self, ds):
        """Processa dados para Carta U (Defeitos por Unidade)."""
        measurements = ds.get("measurements", {})
        if not measurements:
            return None

        # Unidades por amostra (número de unidades inspecionadas por subamostra)
        n_units = ds.get("n_amostra") or ds.get("n")
        if not n_units:
            return None

        # Extrair contagens de defeitos por amostra
        defeitos = []
        for k, v in measurements.items():
            if isinstance(v, list) and len(v) > 0:
                defeitos.append(int(v[0]))
            elif isinstance(v, (int, float)):
                defeitos.append(int(v))

        if not defeitos:
            return None

        m = len(defeitos)
        u_valores = [d / n_units for d in defeitos]
        U_bar = float(np.mean(u_valores))

        # Desvio padrão para u-chart (assumindo n constante)
        dp_u = float(np.sqrt(U_bar / n_units)) if n_units > 0 else 0.0
        lsc_u = float(U_bar + 3 * dp_u)
        lic_u = float(max(0.0, U_bar - 3 * dp_u))

        total_defeitos = sum(defeitos)

        return {
            "chart": "U",
            "U": float(total_defeitos / (n_units * m)),
            "U_bar": float(U_bar),
            "total_defeitos": int(total_defeitos),
            "n": int(n_units),
            "desvio_padrao_u": float(dp_u),
            "lsc_u": float(lsc_u),
            "lic_u": float(lic_u),
            "u_valores": [float(u) for u in u_valores]
        }
    
    def processar_tipo_imr(self, ds):
        """Processa dados para Carta IMR (Individuals and Moving Range)."""
        measurements = ds.get("measurements", {})
        if not measurements:
            return None
        
        # Coletar todos os valores individuais
        valores_individuais = []
        for id_amostra, valores in measurements.items():
            if isinstance(valores, list):
                valores_individuais.extend(valores)
            else:
                valores_individuais.append(valores)
        
        if len(valores_individuais) < 2:
            return None
        
        media_ind = 0
        for valor in valores_individuais:
            media_ind+=valor
        
        media_ind = media_ind/len(valores_individuais)
        media_imr = media_ind

        sigma_ind = 0
        for valor in valores_individuais:
            sigma_ind+=(valor-media_ind)**2
        sigma_ind = math.sqrt(sigma_ind/len(valores_individuais))
        sigma_imr = sigma_ind
        
        # Moving Range (amplitude móvel de 2 pontos)
        mr_values = [abs(valores_individuais[i] - valores_individuais[i-1]) for i in range(1, len(valores_individuais))]
        am_bar = np.mean(mr_values)
        
        # Constantes de controle
        d2 = 1.128  # Para n=2
        lsc_ind = media_ind + 3 * sigma_ind
        lic_ind = media_ind - 3 * sigma_ind
        
        lsc_mr = am_bar * 3.267  # D4 para n=2
        lic_mr = max(0, am_bar * 0)  # D3 para n=2 é 0
        
        return {
            "chart": "IMR",
            "media_ind": float(media_ind),
            "sigma_ind": float(sigma_ind),
            "am_bar": float(am_bar),
            "lsc_ind": float(lsc_ind),
            "lic_ind": float(lic_ind),
            "lsc_mr": float(lsc_mr),
            "lic_mr": float(lic_mr),
            "valores_individuais": [float(v) for v in valores_individuais],
            "mr_values": [float(mr) for mr in mr_values]
        }
    
    def processar_dados(self):
        """Processa todos os dados e gera dados tratados."""
        if not self.datasets:
            print("✗ Nenhum dataset carregado")
            return False
        
        for ds in self.datasets:
            chart_type = ds.get("chart") or ds.get("Chart")
            
            if chart_type == "XR":
                dados = self.processar_tipo_xr(ds)
            elif chart_type == "P":
                dados = self.processar_tipo_p(ds)
            elif chart_type == "U":
                dados = self.processar_tipo_u(ds)
            elif chart_type == "IMR":
                dados = self.processar_tipo_imr(ds)
            else:
                print(f"✗ Tipo de chart não reconhecido: {chart_type}")
                continue
            
            if dados:
                self.dados_tratados.append(dados)
        
        print(f"✓ {len(self.dados_tratados)} dataset(s) processado(s)")
        return True
    
    def salvar_dados_tratados(self):
        """Salva dados tratados em banco_de_dados_tratados e amostras/resultados."""
        # Criar pasta de destino usando raiz do projeto
        pasta_saida = os.path.join(self.raiz_projeto, 'banco_de_dados_tratados')

        if not os.path.exists(pasta_saida):
            os.makedirs(pasta_saida)
            print(f"✓ Pasta criada: {pasta_saida}")

        # Pasta de resultados consumida pela rota /results/cep/<chart>
        pasta_resultados = os.path.join(self.diretorio_script, 'resultados')
        if not os.path.exists(pasta_resultados):
            os.makedirs(pasta_resultados)
            print(f"✓ Pasta criada: {pasta_resultados}")

        # Salvar cada tipo de chart em arquivo separado
        for idx, dados in enumerate(self.dados_tratados):
            chart_type = dados.get("chart")
            nome_arquivo = f"dados_tratados_{chart_type}_{idx}.json"
            caminho_saida = os.path.join(pasta_saida, nome_arquivo)

            with open(caminho_saida, 'w', encoding='utf-8') as f:
                json.dump(dados, f, indent=4, ensure_ascii=False)

            print(f"✓ Dados tratados salvos: {nome_arquivo}")

            # Também salvar em amostras/resultados/<chart>.json (nome simplificado)
            nome_simples = f"{chart_type.lower()}.json"
            caminho_resultado = os.path.join(pasta_resultados, nome_simples)
            with open(caminho_resultado, 'w', encoding='utf-8') as f:
                json.dump(dados, f, indent=4, ensure_ascii=False)
            print(f"✓ Resultado salvo: amostras/resultados/{nome_simples}")

        # Salvar também um índice com todos os dados
        caminho_indice = os.path.join(pasta_saida, 'indice_dados.json')
        with open(caminho_indice, 'w', encoding='utf-8') as f:
            json.dump(self.dados_tratados, f, indent=4, ensure_ascii=False)

        print(f"✓ Índice salvo: indice_dados.json")
        return True
    
    def processar_e_salvar(self, nome_arquivo):
        """Função principal: carrega, processa e salva."""
        if self.carregar_dados_brutos(nome_arquivo):
            if self.processar_dados():
                return self.salvar_dados_tratados()
        return False


if __name__ == "__main__":
    processor = DataProcessor()
    processor.processar_e_salvar('dados_producao.json')