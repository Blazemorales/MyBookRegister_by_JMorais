import numpy as np
import matplotlib.pyplot as plt
import json
import unicodedata
import os
from fpdf import FPDF
import matplotlib
from scipy.stats import norm

matplotlib.use('Agg')

class Cartas:

    @staticmethod
    def obter_caminhos():
        """Define os caminhos baseados na estrutura de pastas."""
        # Define raiz do projeto de forma confiável
        script_dir = os.path.dirname(os.path.abspath(__file__))
        raiz_projeto = os.path.dirname(script_dir)
        
        caminho_dados_tratados = os.path.join(raiz_projeto, 'banco_de_dados_tratados')
        caminho_relatorios = os.path.join(raiz_projeto, 'relatorios')
        
        if not os.path.exists(caminho_relatorios):
            os.makedirs(caminho_relatorios)
            print(f"✓ Pasta criada: {caminho_relatorios}")
            
        return caminho_dados_tratados, caminho_relatorios

    @staticmethod
    def carregar_dados_tratados():
        """Carrega os dados tratados do índice."""
        caminho_dados, _ = Cartas.obter_caminhos()
        caminho_indice = os.path.join(caminho_dados, 'indice_dados.json')
        
        if not os.path.exists(caminho_indice):
            print(f"✗ Arquivo {caminho_indice} não encontrado")
            return None
        
        with open(caminho_indice, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        return dados if isinstance(dados, list) else [dados]

    @staticmethod
    def gerar_pdf_basico(titulo, caminho_img, nome_arquivo_pdf, info_extra=""):
        """Gera PDF genérico com gráfico e informações."""
        _, caminho_relatorios = Cartas.obter_caminhos()
        pdf = FPDF()

        # Tentar usar fonte TrueType UTF-8 (DejaVu Sans) para preservar acentuação.
        # Se não for possível, usar fallback sanitizado compatível com latin-1.
        font_registered = False
        try:
            font_path = matplotlib.font_manager.findfont('DejaVu Sans')
            if font_path and os.path.exists(font_path):
                pdf.add_page()
                pdf.add_font('DejaVu', '', font_path, uni=True)
                pdf.set_font('DejaVu', '', 16)
                titulo_safe = titulo
                info_extra_safe = info_extra
                font_registered = True
        except Exception:
            font_registered = False

        if not font_registered:
            # fallback: sanitizar e usar fonte padrão (latin-1)
            pdf.add_page()
            titulo_safe = Cartas.sanitizar_texto(titulo)
            info_extra_safe = Cartas.sanitizar_texto(info_extra)
            pdf.set_font('Arial', 'B', 16)

        pdf.cell(190, 10, titulo_safe, ln=True, align='C')
        pdf.ln(10)

        # Ajustar fonte para o corpo do texto
        try:
            if font_registered:
                pdf.set_font('DejaVu', '', 11)
            else:
                pdf.set_font('Arial', '', 11)
        except Exception:
            pdf.set_font('Arial', '', 11)

        if info_extra:
            pdf.multi_cell(190, 6, info_extra_safe)
            pdf.ln(5)
        
        if os.path.exists(caminho_img):
            pdf.image(caminho_img, x=10, w=180)
        
        caminho_final = os.path.join(caminho_relatorios, nome_arquivo_pdf)
        pdf.output(caminho_final)
        print(f"✓ PDF gerado: {caminho_final}")
    
    @staticmethod
    def kalman_filter(observacoes, estado_inicial, variancia_processo=None, variancia_medida=None):
        """Filtro de Kalman 1-D (passeio aleatório) para gerar reta de tendência.

        Retorna a série de estimativas a priori. Por construção, o primeiro
        valor é igual a `estado_inicial`, garantindo que a reta comece sobre
        a linha central da carta de controle.
        """
        obs = np.asarray(observacoes, dtype=float)
        n = len(obs)
        if n == 0:
            return np.array([])

        var_obs = float(np.var(obs)) if n > 1 else 1.0
        if variancia_processo is None:
            variancia_processo = max(var_obs * 0.01, 1e-9)
        if variancia_medida is None:
            variancia_medida = max(var_obs, 1e-9)

        Q = float(variancia_processo)
        R = float(variancia_medida)

        x = float(estado_inicial)
        P = R

        a_priori = np.zeros(n)
        for k in range(n):
            if k == 0:
                x_pred, P_pred = x, P
            else:
                x_pred = x
                P_pred = P + Q
            a_priori[k] = x_pred

            K = P_pred / (P_pred + R)
            x = x_pred + K * (obs[k] - x_pred)
            P = (1.0 - K) * P_pred

        return a_priori

    @staticmethod
    def detectar_alertas_montgomery(medias, x_double_bar, sigma):
        """Aplica as 4 regras de Montgomery para pontos fora de controle."""
        n = len(medias)
        alertas = [False] * n
        motivos = [[] for _ in range(n)]

        for i in range(n):
            # REGRA 1: 1 ponto fora dos limites 3-sigma
            if abs(medias[i] - x_double_bar) > 3 * sigma:
                alertas[i] = True
                motivos[i].append("Regra 1: Fora de 3-sigma")

            # Regras de Sensibilidade (Western Electric modificadas por Montgomery)
            if i >= 2:
                # REGRA 2: 2 de 3 pontos consecutivos além de 2-sigma (mesmo lado)
                janela = medias[i-2 : i+1]
                if sum(1 for x in janela if x > x_double_bar + 2*sigma) >= 2 or \
                   sum(1 for x in janela if x < x_double_bar - 2*sigma) >= 2:
                    alertas[i] = True
                    motivos[i].append("Regra 2: 2/3 além de 2-sigma")

            if i >= 4:
                # REGRA 3: 4 de 5 pontos consecutivos além de 1-sigma (mesmo lado)
                janela = medias[i-4 : i+1]
                if sum(1 for x in janela if x > x_double_bar + 1*sigma) >= 4 or \
                   sum(1 for x in janela if x < x_double_bar - 1*sigma) >= 4:
                    alertas[i] = True
                    motivos[i].append("Regra 3: 4/5 além de 1-sigma")

            if i >= 7:
                # REGRA 4: 8 pontos consecutivos do mesmo lado da média
                janela = medias[i-7 : i+1]
                if all(x > x_double_bar for x in janela) or \
                   all(x < x_double_bar for x in janela):
                    alertas[i] = True
                    motivos[i].append("Regra 4: Run de 8 pontos")
        
        return alertas, motivos

    @staticmethod
    def sanitizar_texto(texto: str) -> str:
        """Remove/translitera caracteres Unicode para ASCII compatível com latin-1.

        Usa normalização NFKD e remove marcas diacríticas; converte travessões e aspas especiais.
        """
        if not texto:
            return texto
        # Substituições simples para pontuação que causa problemas
        mapa = {
            '\u2014': '-',  # em dash
            '\u2013': '-',  # en dash
            '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
            '\u2026': '...',
        }
        for k, v in mapa.items():
            texto = texto.replace(k, v)
        # Normalizar e remover diacríticos
        texto_norm = unicodedata.normalize('NFKD', texto)
        texto_ascii = texto_norm.encode('ASCII', 'ignore').decode('ASCII')
        return texto_ascii


    @staticmethod
    def carta_xr(dados_xr=None):
        """Calcula, plota a carta XR e detecta causas especiais."""
        if dados_xr is None:
            todos_dados = Cartas.carregar_dados_tratados()
            if not todos_dados: return False
            dados_xr = next((d for d in todos_dados if d.get("chart") == "XR"), None)
            if not dados_xr: return False
        
        stats = dados_xr.get("estatisticas_por_amostra", [])
        medias = [s["media"] for s in stats]
        amplitudes = [s["amplitude"] for s in stats]
        ids = [s["amostra"] for s in stats]
        
        x_double_bar = dados_xr["x_double_bar"]
        sigma = dados_xr["sigma"]
        r_bar = dados_xr["r_bar"]
        lsc_r, lic_r = dados_xr["lsc_r"], dados_xr["lic_r"]
        
        # Detecção de alertas
        alertas, motivos = Cartas.detectar_alertas_montgomery(medias, x_double_bar, sigma)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # --- Carta X (Médias) ---
        ax1.plot(ids, medias, 'b-', alpha=0.5)
        ax1.plot(ids, medias, 'bo', markersize=6, label='Média')

        # Reta de tendência (Filtro de Kalman) começando na linha central
        kalman_x = Cartas.kalman_filter(medias, x_double_bar)
        ax1.plot(ids, kalman_x, color='darkorange', linestyle='--', linewidth=2,
                 label='Tendência (Kalman)')

        # Destacar Alertas
        indices_alerta = [i for i, v in enumerate(alertas) if v]
        if indices_alerta:
            ax1.plot([ids[i] for i in indices_alerta], [medias[i] for i in indices_alerta],
                     'ro', markersize=10, label='Causa Especial (Montgomery)')

        # Linhas de Controle e Zonas
        ax1.axhline(x_double_bar, color='green', linewidth=2, label='X-barra')
        ax1.axhline(x_double_bar + 3*sigma, color='red', linestyle='-', linewidth=1.5, label='LSC (3σ)')
        ax1.axhline(x_double_bar - 3*sigma, color='red', linestyle='-', linewidth=1.5, label='LIC (3σ)')
        
        # Zonas A e B (tracejadas sutis)
        for s in [1, 2]:
            ax1.axhline(x_double_bar + s*sigma, color='gray', linestyle='--', alpha=0.3)
            ax1.axhline(x_double_bar - s*sigma, color='gray', linestyle='--', alpha=0.3)

        ax1.set_title("Carta X-Bar: Detecção de Causas Especiais", fontsize=14, fontweight='bold')
        ax1.legend(loc='upper right', fontsize='small', ncol=2)
        ax1.grid(True, alpha=0.2)
        
        # --- Carta R (Amplitude) ---
        ax2.plot(ids, amplitudes, 'ro-', linewidth=1, markersize=6, label='Amplitude (R)')
        kalman_r = Cartas.kalman_filter(amplitudes, r_bar)
        ax2.plot(ids, kalman_r, color='darkorange', linestyle='--', linewidth=2,
                 label='Tendência (Kalman)')
        ax2.axhline(r_bar, color='green', label='R-barra')
        ax2.axhline(lsc_r, color='red', linestyle='--', label='LSC_R')
        ax2.axhline(lic_r, color='red', linestyle='--', label='LIC_R')
        ax2.set_title("Carta R (Amplitude)", fontsize=14, fontweight='bold')
        ax2.legend(loc='upper right')
        ax2.grid(True, alpha=0.2)
        
        plt.tight_layout()
        
        _, caminho_relatorios = Cartas.obter_caminhos()
        temp_img = os.path.join(caminho_relatorios, "tmp_xr.png")
        plt.savefig(temp_img, dpi=100)
        plt.close()
        
        # Texto do Relatório
        txt_alertas = ""
        for i in indices_alerta:
            txt_alertas += f"Amostra {ids[i]}: {', '.join(motivos[i])}\n"

        # --- Cálculo da RCP (razão de controle de processo) ---
        # Usa limites de especificação (lse/lie) se existirem no dado tratado.
        lse = dados_xr.get("lse")
        lie = dados_xr.get("lie")
        rcp = None
        rcp_msg = "RCP não calculado: limites de especificação ausentes."
        try:
            if lse is not None and lie is not None and sigma and sigma > 0:
                rcp = (lse - lie) / (6.0 * sigma)
                # Interpretação simples baseada em Montgomery (Cp ~ razão capacidade)
                tol = 1e-6
                if rcp > 1.0 + tol:
                    rcp_msg = "RCP > 1: Processo capaz — está tranquilo."
                elif abs(rcp - 1.0) <= tol:
                    rcp_msg = "RCP = 1: Pode haver possibilidade de produtos com defeitos."
                else:
                    rcp_msg = "RCP < 1: Altas chances de produtos defeituosos."
        except Exception:
            rcp_msg = "Erro ao calcular RCP." 

        rcp_str = f"{rcp:.6f}" if rcp is not None else "N/A"

        info = f"""Resumo da Analise XR (Causas Especiais):

    Media: {x_double_bar:.4f} | Sigma: {sigma:.4f}
    Limites de Controle (3-sigma): [{x_double_bar - 3*sigma:.4f} , {x_double_bar + 3*sigma:.4f}]

    Alertas Identificados:
    {txt_alertas if txt_alertas else 'Nenhum ponto fora de controle detectado.'}

    RCP (Razão de Controle de Processo): {rcp_str}
    Interpretação: {rcp_msg}
    """
        Cartas.gerar_pdf_basico("Relatorio de Controle Estatistico - Montgomery", temp_img, "relatorio_XR.pdf", info)
        if os.path.exists(temp_img): os.remove(temp_img)
        return True
    
    @staticmethod
    def carta_p(dados_p=None):
        """Calcula e plota a carta P (Proporção de Defeituosos)."""
        if dados_p is None:
            todos_dados = Cartas.carregar_dados_tratados()
            if not todos_dados:
                # Gerar PDF placeholder informando ausência de dados
                _, caminho_relatorios = Cartas.obter_caminhos()
                info = "Nenhum dado tratado para carta P foi encontrado. Forneca um arquivo bruto com Chart='P'."
                Cartas.gerar_pdf_basico("Relatorio Carta P - Vazio", "", "relatorio_P.pdf", info)
                print("⚠️ PDF placeholder para P gerado (sem dados)")
                return True
            dados_p = next((d for d in todos_dados if d.get("chart") == "P"), None)
            if not dados_p:
                _, caminho_relatorios = Cartas.obter_caminhos()
                info = "Nenhum dado tratado para carta P foi encontrado. Forneca um arquivo bruto com Chart='P'."
                Cartas.gerar_pdf_basico("Relatorio Carta P - Vazio", "", "relatorio_P.pdf", info)
                print("⚠️ PDF placeholder para P gerado (sem dados)")
                return True
        
        proporcoes = dados_p.get("proporcoes", [])
        P_bar = dados_p["P_bar"]
        lsc_P = dados_p["lsc_P"]
        lic_P = dados_p["lic_P"]
        N = dados_p["N"]
        
        ids = [str(i+1) for i in range(len(proporcoes))]
        
        plt.figure(figsize=(12, 6))
        plt.plot(ids, proporcoes, 'go-', linewidth=2, markersize=8, label='Proporção')
        kalman_p = Cartas.kalman_filter(proporcoes, P_bar)
        plt.plot(ids, kalman_p, color='darkorange', linestyle='--', linewidth=2,
                 label='Tendência (Kalman)')
        plt.axhline(P_bar, color='blue', linestyle='-', linewidth=2, label='P-barra')
        plt.axhline(lsc_P, color='red', linestyle='--', linewidth=2, label='LSC')
        plt.axhline(lic_P, color='red', linestyle='--', linewidth=2, label='LIC')
        plt.title("Carta de Controle P (Proporção de Defeituosos)", fontsize=14, fontweight='bold')
        plt.xlabel("Amostra")
        plt.ylabel("Proporção de Defeituosos")
        plt.legend(loc='upper right')
        plt.grid(True, alpha=0.3)
        
        _, caminho_relatorios = Cartas.obter_caminhos()
        temp_img = os.path.join(caminho_relatorios, "tmp_p.png")
        plt.savefig(temp_img, dpi=100, bbox_inches='tight')
        plt.close()

        info = f"""Resumo da Analise P:

    Proporção Media (P-barra): {P_bar:.6f}
    Proporção (P): {dados_p.get('P', 0.0):.6f}
    Total de Defeitos (D): {dados_p.get('total_defeitos', 'N/A')}
    Tamanho do Lote (N): {N}

    Limites de Controle:
      LSC = {lsc_P:.6f}
      LIC = {lic_P:.6f}

    Desvio Padrao: {dados_p.get('desvio_padrao_p', 0.0):.6f}
    Numero de amostras: {len(proporcoes)}"""

        Cartas.gerar_pdf_basico("Relatorio de Controle - Carta P", temp_img, "relatorio_P.pdf", info)
        if os.path.exists(temp_img):
            os.remove(temp_img)
        return True
    
    @staticmethod
    def carta_u(dados_u=None):
        """Calcula e plota a carta U (Defeitos por Unidade)."""
        if dados_u is None:
            todos_dados = Cartas.carregar_dados_tratados()
            if not todos_dados:
                # Gerar PDF placeholder informando ausência de dados
                _, caminho_relatorios = Cartas.obter_caminhos()
                info = "Nenhum dado tratado para carta U foi encontrado. Forneca um arquivo bruto com Chart='U'."
                Cartas.gerar_pdf_basico("Relatorio Carta U - Vazio", "", "relatorio_U.pdf", info)
                print("⚠️ PDF placeholder para U gerado (sem dados)")
                return True
            dados_u = next((d for d in todos_dados if d.get("chart") == "U"), None)
            if not dados_u:
                _, caminho_relatorios = Cartas.obter_caminhos()
                info = "Nenhum dado tratado para carta U foi encontrado. Forneca um arquivo bruto com Chart='U'."
                Cartas.gerar_pdf_basico("Relatorio Carta U - Vazio", "", "relatorio_U.pdf", info)
                print("⚠️ PDF placeholder para U gerado (sem dados)")
                return True
        
        u_valores = dados_u.get("u_valores", [])
        U_bar = dados_u["U_bar"]
        lsc_u = dados_u["lsc_u"]
        lic_u = dados_u["lic_u"]
        n = dados_u["n"]
        
        ids = [str(i+1) for i in range(len(u_valores))]
        
        plt.figure(figsize=(12, 6))
        plt.plot(ids, u_valores, 'mo-', linewidth=2, markersize=8, label='u (Defeitos/Unidade)')
        kalman_u = Cartas.kalman_filter(u_valores, U_bar)
        plt.plot(ids, kalman_u, color='darkorange', linestyle='--', linewidth=2,
                 label='Tendência (Kalman)')
        plt.axhline(U_bar, color='blue', linestyle='-', linewidth=2, label='U-barra')
        plt.axhline(lsc_u, color='red', linestyle='--', linewidth=2, label='LSC')
        plt.axhline(lic_u, color='red', linestyle='--', linewidth=2, label='LIC')
        plt.title("Carta de Controle U (Defeitos por Unidade)", fontsize=14, fontweight='bold')
        plt.xlabel("Amostra")
        plt.ylabel("Defeitos por Unidade")
        plt.legend(loc='upper right')
        plt.grid(True, alpha=0.3)
        
        _, caminho_relatorios = Cartas.obter_caminhos()
        temp_img = os.path.join(caminho_relatorios, "tmp_u.png")
        plt.savefig(temp_img, dpi=100, bbox_inches='tight')
        plt.close()

        info = f"""Resumo da Analise U:

    Media de Defeitos por Unidade (U-barra): {U_bar:.6f}
    Defeitos por Unidade (U): {dados_u.get('U', 0.0):.6f}
    Total de Defeitos (C): {dados_u.get('total_defeitos', 'N/A')}
    Numero de Unidades (n): {n}

    Limites de Controle:
      LSC = {lsc_u:.6f}
      LIC = {lic_u:.6f}

    Desvio Padrao: {dados_u.get('desvio_padrao_u', 0.0):.6f}
    Numero de amostras: {len(u_valores)}"""

        Cartas.gerar_pdf_basico("Relatorio de Controle - Carta U", temp_img, "relatorio_U.pdf", info)
        if os.path.exists(temp_img):
            os.remove(temp_img)
        return True
    
    @staticmethod
    def carta_imr(dados_imr=None):
        """Calcula e plota a carta IMR (Individuals and Moving Range)."""
        if dados_imr is None:
            todos_dados = Cartas.carregar_dados_tratados()
            if not todos_dados:
                return False
            dados_imr = next((d for d in todos_dados if d.get("chart") == "IMR"), None)
            if not dados_imr:
                print("✗ Nenhum dado IMR encontrado")
                return False
        
        valores_ind = dados_imr.get("valores_individuais", [])
        mr_values = dados_imr.get("mr_values", [])
        media_ind = dados_imr["media_ind"]
        lsc_ind = dados_imr["lsc_ind"]
        lic_ind = dados_imr["lic_ind"]
        am_bar = dados_imr["am_bar"]
        lsc_mr = dados_imr["lsc_mr"]
        lic_mr = dados_imr["lic_mr"]
        
        ids = [str(i+1) for i in range(len(valores_ind))]
        ids_mr = [str(i+1) for i in range(len(mr_values))]
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # Carta I (Individuais)
        ax1.plot(ids, valores_ind, 'co-', linewidth=2, markersize=8, label='Valor Individual')
        kalman_i = Cartas.kalman_filter(valores_ind, media_ind)
        ax1.plot(ids, kalman_i, color='darkorange', linestyle='--', linewidth=2,
                 label='Tendência (Kalman)')
        ax1.axhline(media_ind, color='blue', linestyle='-', linewidth=2, label='Média')
        ax1.axhline(lsc_ind, color='red', linestyle='--', linewidth=2, label='LSC')
        ax1.axhline(lic_ind, color='red', linestyle='--', linewidth=2, label='LIC')
        ax1.set_title("Carta de Controle I (Valores Individuais)", fontsize=14, fontweight='bold')
        ax1.set_ylabel("Valor")
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)
        
        # Carta MR (Moving Range)
        ax2.plot(ids_mr, mr_values, 'yo-', linewidth=2, markersize=8, label='Moving Range')
        kalman_mr = Cartas.kalman_filter(mr_values, am_bar)
        ax2.plot(ids_mr, kalman_mr, color='darkorange', linestyle='--', linewidth=2,
                 label='Tendência (Kalman)')
        ax2.axhline(am_bar, color='blue', linestyle='-', linewidth=2, label='MR-barra')
        ax2.axhline(lsc_mr, color='red', linestyle='--', linewidth=2, label='LSC_MR')
        ax2.axhline(lic_mr, color='red', linestyle='--', linewidth=2, label='LIC_MR')
        ax2.set_title("Carta de Controle MR (Moving Range)", fontsize=14, fontweight='bold')
        ax2.set_xlabel("Amostra")
        ax2.set_ylabel("Moving Range")
        ax2.legend(loc='upper right')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        _, caminho_relatorios = Cartas.obter_caminhos()
        temp_img = os.path.join(caminho_relatorios, "tmp_imr.png")
        plt.savefig(temp_img, dpi=100, bbox_inches='tight')
        plt.close()
        
        info = f"""Resumo da Analise IMR:

Media dos Individuais: {media_ind:.4f}
Desvio Padrao: {dados_imr['sigma_ind']:.4f}

Limites de Controle I:
  LSC = {lsc_ind:.4f}
  LIC = {lic_ind:.4f}

Moving Range Media (MR-barra): {am_bar:.4f}

Limites de Controle MR:
  LSC_MR = {lsc_mr:.4f}
  LIC_MR = {lic_mr:.4f}

Numero de observacoes: {len(valores_ind)}
Numero de MR: {len(mr_values)}"""
        
        Cartas.gerar_pdf_basico("Relatorio de Controle - Carta IMR", temp_img, "relatorio_IMR.pdf", info)
        if os.path.exists(temp_img):
            os.remove(temp_img)
        return True
    
    @staticmethod
    def gerar_todos_relatorios():
        """Gera relatórios para todos os tipos de chart disponíveis."""
        print("\n" + "="*60)
        print("GERANDO RELATÓRIOS DE CONTROLE")
        print("="*60 + "\n")
        
        todos_dados = Cartas.carregar_dados_tratados()
        if not todos_dados:
            print("✗ Nenhum dado tratado encontrado")
            return False
        
        resultados = {"sucesso": 0, "erro": 0}
        
        for dados in todos_dados:
            chart_type = dados.get("chart")
            print(f"\n[{chart_type}] Processando...")
            
            try:
                if chart_type == "XR":
                    if Cartas.carta_xr(dados):
                        resultados["sucesso"] += 1
                elif chart_type == "P":
                    if Cartas.carta_p(dados):
                        resultados["sucesso"] += 1
                elif chart_type == "U":
                    if Cartas.carta_u(dados):
                        resultados["sucesso"] += 1
                elif chart_type == "IMR":
                    if Cartas.carta_imr(dados):
                        resultados["sucesso"] += 1
                else:
                    print(f"  ✗ Tipo não reconhecido: {chart_type}")
                    resultados["erro"] += 1
            except Exception as e:
                print(f"  ✗ Erro ao processar {chart_type}: {str(e)}")
                resultados["erro"] += 1
        
        print("\n" + "="*60)
        print(f"RESULTADO: {resultados['sucesso']} sucesso(s), {resultados['erro']} erro(s)")
        print("="*60 + "\n")
        
        return resultados["erro"] == 0