import json
import math
import os
import numpy as np
from scipy.stats import norm

# Tabela de constantes A2/D3/D4/d2 (fonte unica). Tenta o import de pacote e,
# em execucao standalone, cai para o arquivo irmao em ../constantes.py.
try:
    from code.backend.CEP.constantes import constantes as _constantes
except Exception:  # pragma: no cover - fallback para execucao direta
    import importlib.util
    _const_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "constantes.py"
    )
    _spec = importlib.util.spec_from_file_location("cep_constantes", _const_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _constantes = _mod.constantes

# Fórmulas de capacidade (Cp/Cpk, 16-21) — fonte única em ../analise.py.
try:
    from code.backend.CEP import analise as _analise
except Exception:  # pragma: no cover - fallback para execucao direta
    import importlib.util
    _an_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analise.py"
    )
    _an_spec = importlib.util.spec_from_file_location("cep_analise", _an_path)
    _analise = importlib.util.module_from_spec(_an_spec)
    _an_spec.loader.exec_module(_analise)


import operator
import re

_OPS_CRITERIO = {
    "<=": operator.le, ">=": operator.ge,
    "<": operator.lt, ">": operator.gt,
    "==": operator.eq, "!=": operator.ne,
}


def parse_criterio_defeito(criterio):
    """Converte uma string como 'x < 49.00' / 'x >= 51,2' num predicado f(valor)->bool.

    Aceita os operadores < <= > >= == !=. Retorna None se não houver critério
    reconhecível (aí o dado é tratado como contagem de defeitos já pronta).
    """
    if not isinstance(criterio, str):
        return None
    m = re.search(r"([<>!=]=|[<>])\s*(-?\d+(?:[.,]\d+)?)", criterio)
    if not m:
        return None
    op = _OPS_CRITERIO.get(m.group(1))
    if op is None:
        return None
    limite = float(m.group(2).replace(",", "."))
    return lambda x: op(float(x), limite)


def normalizar_dataset(ds):
    """Aceita o formato do professor e devolve um dataset canônico.

    Mapeia, preservando todos os valores brutos:
      Carta/Chart        -> chart   (e 'MRI' -> 'IMR')
      Amostras/amostras  -> measurements
      Defeituosos        -> criterio_defeito

    Idempotente: datasets já canônicos passam intactos.
    """
    if not isinstance(ds, dict):
        return ds
    out = dict(ds)

    chart = out.get("chart") or out.get("Chart") or out.get("Carta")
    if chart:
        chart = str(chart).strip().upper()
        if chart == "MRI":  # nomenclatura do enunciado == IMR no código
            chart = "IMR"
        out["chart"] = chart

    meas = out.get("measurements")
    if meas is None:
        meas = out.get("Amostras") or out.get("amostras")
        if meas is not None:
            out["measurements"] = meas

    criterio = out.get("criterio_defeito") or out.get("Defeituosos")
    if criterio is not None:
        out["criterio_defeito"] = criterio

    return out


def ler_especificacoes(ds):
    """Lê LIE/LSE explícitos do dataset, em várias grafias.

    Retorna (lie, lse) como floats, ou (None, None) quando não há
    especificação utilizável (ausente, não numérica, zerada ou invertida).
    """
    lse = ds.get("Limite sup. Esp", ds.get("lse", ds.get("LSE")))
    lie = ds.get("Limite inf. Esp", ds.get("lie", ds.get("LIE")))
    try:
        lse = float(lse) if lse is not None else None
        lie = float(lie) if lie is not None else None
    except (TypeError, ValueError):
        return None, None
    if lse is None or lie is None or (lse == 0 and lie == 0) or lse <= lie:
        return None, None
    return lie, lse


def calcular_capacidade(mu, sigma, lic, lsc, lie=None, lse=None):
    """Capacidade do processo (Cp/Cpk, fórmula 16-21) com especificação autônoma.

    Usa LIE/LSE quando informados; na ausência, deriva-os dos limites de
    controle (LIE = 0.99*LIC, LSE = 1.2*LSC — mesma convenção da Questão 1,
    via analise.capacidade_por_limites). Retorna None se sigma <= 0.
    """
    if not sigma or sigma <= 0:
        return None
    if lie is not None and lse is not None:
        origem = "especificacao_informada"
    else:
        lie = 0.99 * lic
        lse = 1.2 * lsc
        origem = "derivada_dos_limites_de_controle"
    return {
        "lie": float(lie),
        "lse": float(lse),
        "cp": float(_analise.cp(sigma, lse, lie)),
        "cpk": float(_analise.cpk(mu, sigma, lse, lie)),
        "origem_especificacao": origem,
    }


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
        """Carrega datasets brutos de um ou vários arquivos JSON.

        nome_arquivo pode ser:
          - None ou str  → arquivo único em banco_de_dados_amostras/ (comportamento original)
          - list[str]    → caminhos absolutos (ex.: ["/...xr.json", "/...mri.json",
                           "/...atributos.json"]) para os 3 arquivos separados do professor
        """
        if isinstance(nome_arquivo, list):
            return self._carregar_lista_arquivos(nome_arquivo)

        arquivo_para_abrir = nome_arquivo or self.nome_arquivo_padrao

        caminho_completo = os.path.join(
            self.diretorio_script,
            'banco_de_dados_amostras',
            arquivo_para_abrir,
        )

        try:
            with open(caminho_completo, 'r', encoding='utf-8') as f:
                conteudo = json.load(f)
            self.datasets = conteudo if isinstance(conteudo, list) else [conteudo]
            print(f"✓ Dados brutos carregados: {arquivo_para_abrir}")
            self._logar_tipos()
            return True
        except FileNotFoundError:
            print(f"✗ Arquivo não encontrado: {caminho_completo}")
            return False
        except json.JSONDecodeError:
            print(f"✗ JSON inválido: {arquivo_para_abrir}")
            return False
        except Exception as e:
            print(f"✗ Erro ao carregar {arquivo_para_abrir}: {e}")
            return False

    # Tipos de carta esperados quando carregando os 3 arquivos do professor.
    _TIPOS_OBRIGATORIOS = {"XR", "IMR", "P", "U"}

    # Mapa nome-de-arquivo → tipo de carta (usado quando o JSON não tem campo chart).
    _CHART_POR_NOME = {
        "xr.json": "XR",
        "mri.json": "IMR",
    }

    def _carregar_lista_arquivos(self, caminhos):
        """Carrega e concatena múltiplos arquivos JSON (formato 3-arquivos do professor)."""
        datasets = []
        for caminho in caminhos:
            nome = os.path.basename(caminho).lower()
            chart_inferido = self._CHART_POR_NOME.get(nome)
            try:
                with open(caminho, 'r', encoding='utf-8') as f:
                    conteudo = json.load(f)
            except FileNotFoundError:
                print(f"✗ Arquivo não encontrado: {caminho}")
                return False
            except json.JSONDecodeError:
                print(f"✗ JSON inválido: {caminho}")
                return False

            items = conteudo if isinstance(conteudo, list) else [conteudo]
            for item in items:
                if not isinstance(item, dict):
                    continue
                # Injeta o tipo quando o JSON não traz campo chart e o nome é reconhecido.
                if chart_inferido and not (item.get("chart") or item.get("Chart")):
                    item["chart"] = chart_inferido
                datasets.append(item)
            print(f"✓ Carregado: {os.path.basename(caminho)} ({len(items)} dataset(s))")

        self.datasets = datasets
        return self._logar_tipos(required=self._TIPOS_OBRIGATORIOS)

    def _logar_tipos(self, required=None):
        """Loga os tipos encontrados; aborta se algum tipo obrigatório estiver faltando."""
        from collections import Counter
        tipos = Counter(
            normalizar_dataset(ds).get("chart", "?")
            for ds in self.datasets
        )
        print(f"   Tipos carregados: { {k: v for k, v in sorted(tipos.items())} }")
        if required:
            faltando = required - set(tipos.keys())
            if faltando:
                print(f"✗ Tipos obrigatórios ausentes: {sorted(faltando)}")
                print("  Verifique se os 3 arquivos foram passados corretamente.")
                return False
        return True
    
    def processar_tipo_xr(self, ds):
        """Processa dados para Carta XR (Médias e Amplitudes)."""
        measurements = ds.get("measurements", {})
        if not measurements:
            return None
        
        lie_esp, lse_esp = ler_especificacoes(ds)


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

        # Tamanho do subgrupo (assume n constante; usa o mais frequente).
        tamanhos = [s["n"] for s in estatisticas_por_amostra]
        n_amostra = int(max(set(tamanhos), key=tamanhos.count)) if tamanhos else len(valores)

        # Constantes tabeladas para este n (fórmulas 16-9 e 16-12).
        A2, D3, D4, d2 = _constantes(n_amostra)

        # Sigma do PROCESSO (individuais) estimado pelo alcance: sigma_hat = r_bar/d2.
        # Usado em capacidade e cálculos probabilísticos.
        sigma_individual = (r_bar / d2) if d2 else 0.0

        # Sigma da MÉDIA do subgrupo (erro padrão): sigma_xbar = sigma_hat/sqrt(n)
        # = A2*r_bar/3. Guardado em "sigma" para que x_bb ± 3*sigma == x_bb ± A2*r_bar,
        # mantendo coerentes os limites, as zonas 1/2/3-sigma e as regras de Montgomery.
        sigma_xbar = (A2 * r_bar / 3.0) if r_bar else 0.0

        # Carta X (16-9)
        lsc_x = x_double_bar + A2 * r_bar
        lic_x = x_double_bar - A2 * r_bar
        # Carta R (16-12)
        lsc_r = D4 * r_bar
        lic_r = D3 * r_bar

        # Capacidade: especificação do dataset ou derivada das cartas (autônoma).
        capacidade = calcular_capacidade(
            x_double_bar, sigma_individual, lic_x, lsc_x, lie_esp, lse_esp
        )

        return {
            "chart": "XR",
            "lse": float(capacidade["lse"]) if capacidade else float(lse_esp or 0.0),
            "lie": float(capacidade["lie"]) if capacidade else float(lie_esp or 0.0),
            "capacidade": capacidade,
            "x_double_bar": float(x_double_bar),
            "r_bar": float(r_bar),
            "sigma": float(sigma_xbar),
            "sigma_individual": float(sigma_individual),
            "A2": float(A2),
            "D3": float(D3),
            "D4": float(D4),
            "d2": float(d2),
            "lsc_x": float(lsc_x),
            "lic_x": float(lic_x),
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

        # Critério de defeito (ex.: "x < 49.00"): quando presente, as amostras são
        # medições brutas e contamos por amostra quantas violam o critério.
        criterio_str = ds.get("criterio_defeito")
        pred = parse_criterio_defeito(criterio_str)

        defeitos = []
        if pred is not None:
            for k, v in measurements.items():
                valores = v if isinstance(v, list) else [v]
                defeitos.append(sum(1 for x in valores if pred(x)))
                if not N:  # N inferido do tamanho da subamostra
                    N = len(valores)
        else:
            # Caminho clássico: cada entrada já é a contagem de defeituosos.
            for k, v in measurements.items():
                if isinstance(v, list) and len(v) > 0:
                    defeitos.append(int(v[0]))
                elif isinstance(v, (int, float)):
                    defeitos.append(int(v))

        if not N or not defeitos:
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
            "proporcoes": [float(p) for p in proporcoes],
            "criterio_defeito": criterio_str,
            "defeitos_por_amostra": [int(d) for d in defeitos],
        }
    
    def processar_tipo_u(self, ds):
        """Processa dados para Carta U (Defeitos por Unidade)."""
        measurements = ds.get("measurements", {})
        if not measurements:
            return None

        # Unidades por amostra (número de unidades inspecionadas por subamostra)
        n_units = ds.get("n_amostra") or ds.get("n")

        # Critério de defeito (ex.: "x < 49.00"): quando presente, as amostras são
        # medições brutas e contamos por amostra quantas violam o critério.
        criterio_str = ds.get("criterio_defeito")
        pred = parse_criterio_defeito(criterio_str)

        defeitos = []
        if pred is not None:
            for k, v in measurements.items():
                valores = v if isinstance(v, list) else [v]
                defeitos.append(sum(1 for x in valores if pred(x)))
                if not n_units:  # n inferido do tamanho da subamostra
                    n_units = len(valores)
        else:
            # Caminho clássico: cada entrada já é a contagem de defeitos.
            for k, v in measurements.items():
                if isinstance(v, list) and len(v) > 0:
                    defeitos.append(int(v[0]))
                elif isinstance(v, (int, float)):
                    defeitos.append(int(v))

        if not n_units or not defeitos:
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
            "u_valores": [float(u) for u in u_valores],
            "criterio_defeito": criterio_str,
            "defeitos_por_amostra": [int(d) for d in defeitos],
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

        # Moving Range (amplitude móvel de 2 pontos)
        mr_values = [abs(valores_individuais[i] - valores_individuais[i-1]) for i in range(1, len(valores_individuais))]
        am_bar = np.mean(mr_values)

        # Constantes para n=2 (par usado no moving range).
        _, D3, D4, d2 = _constantes(2)

        # Carta I (16-19): sigma estimado pelo alcance móvel, sigma_hat = am_bar/d2,
        # NÃO o desvio amostral dos individuais.
        sigma_ind = (am_bar / d2) if d2 else 0.0
        sigma_imr = sigma_ind
        lsc_ind = media_ind + 3 * sigma_ind
        lic_ind = media_ind - 3 * sigma_ind

        # Carta MR: LSC = D4*am_bar, LIC = D3*am_bar (D3=0 para n=2).
        lsc_mr = D4 * am_bar
        lic_mr = max(0.0, D3 * am_bar)

        # Capacidade: especificação do dataset ou derivada das cartas (autônoma).
        lie_esp, lse_esp = ler_especificacoes(ds)
        capacidade = calcular_capacidade(
            media_ind, sigma_ind, lic_ind, lsc_ind, lie_esp, lse_esp
        )

        return {
            "chart": "IMR",
            "lse": float(capacidade["lse"]) if capacidade else float(lse_esp or 0.0),
            "lie": float(capacidade["lie"]) if capacidade else float(lie_esp or 0.0),
            "capacidade": capacidade,
            "media_ind": float(media_ind),
            "sigma_ind": float(sigma_ind),
            "sigma_individual": float(sigma_ind),
            "d2": float(d2),
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
            ds = normalizar_dataset(ds)
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