"""Gera a entrega do simulado CEP no layout exigido pelo professor.

Produz:
    <matricula>.zip
      |__ data/    xr.json, mri.json, atributos.json   (dados de entrada)
      |__ code/    cópia do código-fonte executável
      |__ report/  response_<matricula>.pdf            (respostas Q1 e Q2)

Uso:
    python3 code/backend/CEP/gerar_entrega.py [matricula] [arquivo_dados.json]

O `arquivo_dados.json` deve estar em amostras/banco_de_dados_amostras/ e conter
uma lista de datasets com `Chart` ∈ {XR, IMR, P, U}. Sem argumentos, usa a
matrícula "000000000" e o dataset de exemplo `dados_producao_total.json`.

Os cálculos das respostas estão em `analise.py`; os limites das cartas em
`amostras/data_processor.py`; os gráficos/PDFs em `cartas_controle/Cartas.py`.
"""

import importlib.util
import os
import shutil
import sys
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))

# Parâmetros centralizados em parametros_enunciado.py — não duplicar aqui.
def _carregar(nome, caminho_rel):
    """Carrega um módulo por caminho de arquivo (evita conflito com stdlib `code`)."""
    caminho = os.path.join(AQUI, caminho_rel)
    spec = importlib.util.spec_from_file_location(nome, caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_params = _carregar("cep_params", "parametros_enunciado.py")
PPM_REQUERIDO     = _params.PPM_REQUERIDO
MARGEM_ALVO       = _params.MARGEM_ALVO
DESLOCAMENTO_SIGMA = _params.DESLOCAMENTO_SIGMA
BINOM_K           = _params.BINOM_K
BINOM_N           = _params.BINOM_N
FATOR_LIE         = _params.FATOR_LIE
FATOR_LSE         = _params.FATOR_LSE


analise = _carregar("cep_analise", "analise.py")
_dp = _carregar("cep_data_processor", os.path.join("amostras", "data_processor.py"))
_cartas = _carregar("cep_cartas", os.path.join("cartas_controle", "Cartas.py"))
DataProcessor = _dp.DataProcessor
Cartas = _cartas.Cartas


# ---------------------------------------------------------------------------
# Respostas da Questão 1 (cartas de variáveis: XR e IMR)
# ---------------------------------------------------------------------------
def responder_variaveis(d, ppm_req=PPM_REQUERIDO, rend_alvo=MARGEM_ALVO,
                        desloc=DESLOCAMENTO_SIGMA, k_binom=BINOM_K, n_binom=BINOM_N,
                        fator_lie=FATOR_LIE, fator_lse=FATOR_LSE):
    """Monta o bloco de respostas para uma carta de variáveis (XR ou IMR)."""
    chart = d["chart"]
    if chart == "XR":
        mu = d["x_double_bar"]
        sigma = d["sigma_individual"]
        lic, lsc = d["lic_x"], d["lsc_x"]
        valores = [s["media"] for s in d["estatisticas_por_amostra"]]
    else:  # IMR
        mu = d["media_ind"]
        sigma = d["sigma_individual"]
        lic, lsc = d["lic_ind"], d["lsc_ind"]
        valores = d["valores_individuais"]

    cap = analise.capacidade_por_limites(mu, sigma, lic, lsc, fator_lie, fator_lse)
    lie, lse = cap["lie"], cap["lse"]

    curto = analise.sob_controle_curto_prazo(valores, lic, lsc)
    longo = analise.atende_longo_prazo(mu, sigma, lse, lie, ppm_req)
    rend = analise.rendimento(mu, sigma, lse, lie)
    x_alvo = analise.quantil_para_rendimento(mu, sigma, rend_alvo, lado="superior")
    x_alvo_central = analise.quantil_para_rendimento(mu, sigma, rend_alvo, lado="central")
    rend_desloc = analise.rendimento_com_deslocamento(mu, sigma, lse, lie, desloc)
    binom = analise.prob_binomial(k_binom, n_binom, rend)

    linhas = []
    linhas.append(f"=== Carta {chart} ===")
    linhas.append(f"Media (mu): {mu:.4f} | Sigma processo (r_bar/d2): {sigma:.4f}")
    linhas.append(f"Limites de controle: LIC={lic:.4f} | LSC={lsc:.4f}")
    linhas.append(f"Especificacoes derivadas: LIE={fator_lie:g}*LIC={lie:.4f} | LSE={fator_lse:g}*LSC={lse:.4f}")
    linhas.append("")
    linhas.append("a) Curto prazo (1 ponto fora de +/-3sigma): "
                  + ("SOB CONTROLE" if curto["sob_controle"]
                     else f"FORA DE CONTROLE em {len(curto['pontos_fora'])} ponto(s)"))
    linhas.append(f"b) Longo prazo: ppm obtido={longo['ppm_obtido']:.2f} vs requerido={ppm_req:.0f} -> "
                  + ("ATENDE" if longo["atende"] else "NAO ATENDE"))
    linhas.append(f"c) Valor de X p/ {rend_alvo*100:g}% de sucesso: "
                  f"percentil={x_alvo:.4f} | intervalo central=[{x_alvo_central[0]:.4f}, {x_alvo_central[1]:.4f}]")
    linhas.append(f"d) Capacidade (centralizada): Cp={cap['cp']:.4f} | Cpk={cap['cpk']:.4f}")
    linhas.append(f"e) Margem de sucesso atual: {rend*100:.4f}%")
    linhas.append(f"f) Margem de sucesso com deslocamento de +{desloc:g}sigma: {rend_desloc*100:.4f}%")
    linhas.append(f"g) Binomial: P(X={k_binom} em {n_binom} | p={rend:.4f}): "
                  f"exata={binom['exata']:.6f} | P(>= {k_binom})={binom['ao_menos']:.6f}")
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Respostas da Questão 2 (cartas de atributos P e U, mesmo JSON)
# ---------------------------------------------------------------------------
def responder_atributos(dados_p, dados_u):
    """Monta o bloco de respostas para P e U (Questão 2)."""
    linhas = ["=== Cartas de Atributos (mesmo JSON) ==="]
    if dados_p:
        ctrl = analise.sob_controle_curto_prazo(
            dados_p["proporcoes"], dados_p["lic_P"], dados_p["lsc_P"])
        kal = Cartas.kalman_filter(dados_p["proporcoes"], dados_p["P_bar"])
        desloc = Cartas.aviso_deslocamento_kalman(kal, dados_p["P_bar"], "Carta P")
        linhas.append(f"[P] P-barra={dados_p['P_bar']:.6f} | LIC={dados_p['lic_P']:.6f} | LSC={dados_p['lsc_P']:.6f}")
        linhas.append("    Curto prazo: " + ("SOB CONTROLE" if ctrl["sob_controle"]
                      else f"FORA em {len(ctrl['pontos_fora'])} ponto(s)"))
        linhas.append("    Deslocamento: " + (desloc if desloc else "Nenhum deslocamento significativo (Kalman)."))
    if dados_u:
        ctrl = analise.sob_controle_curto_prazo(
            dados_u["u_valores"], dados_u["lic_u"], dados_u["lsc_u"])
        kal = Cartas.kalman_filter(dados_u["u_valores"], dados_u["U_bar"])
        desloc = Cartas.aviso_deslocamento_kalman(kal, dados_u["U_bar"], "Carta U")
        linhas.append(f"[U] U-barra={dados_u['U_bar']:.6f} | LIC={dados_u['lic_u']:.6f} | LSC={dados_u['lsc_u']:.6f}")
        linhas.append("    Curto prazo: " + ("SOB CONTROLE" if ctrl["sob_controle"]
                      else f"FORA em {len(ctrl['pontos_fora'])} ponto(s)"))
        linhas.append("    Deslocamento: " + (desloc if desloc else "Nenhum deslocamento significativo (Kalman)."))
    return "\n".join(linhas)


def processar_atributos_mesmo_json(processor, ds):
    """Q2: o MESMO dataset alimenta a carta P e a carta U."""
    dados_p = processor.processar_tipo_p(ds)
    dados_u = processor.processar_tipo_u(ds)
    return dados_p, dados_u


# ---------------------------------------------------------------------------
# Montagem do PDF de respostas e do ZIP de entrega
# ---------------------------------------------------------------------------
def gerar_response_pdf(matricula, blocos, imagens, destino):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(190, 10, Cartas.sanitizar_texto(
        f"Respostas - Simulado CEP - Matricula {matricula}"), ln=True, align="C")
    pdf.ln(4)
    pdf.set_font("Arial", "", 10)
    for bloco in blocos:
        pdf.multi_cell(190, 5, Cartas.sanitizar_texto(bloco))
        pdf.ln(3)
    for titulo, caminho in imagens:
        if os.path.exists(caminho):
            pdf.add_page()
            pdf.set_font("Arial", "B", 12)
            pdf.cell(190, 8, Cartas.sanitizar_texto(titulo), ln=True)
            pdf.image(caminho, x=10, w=180)
    pdf.output(destino)
    print(f"✓ Response PDF gerado: {destino}")


def main(matricula="000000000", arquivo_dados="dados_producao_total.json"):
    print(f"\n=== Gerando entrega para matricula {matricula} ===")
    rel_dir = os.path.join(AQUI, "relatorios")
    os.environ["CEP_KEEP_PNG"] = "1"  # preserva PNGs das cartas p/ embutir no response

    # 1) Processa os dados e salva tratados
    processor = DataProcessor()
    if not processor.carregar_dados_brutos(arquivo_dados):
        return False
    processor.processar_dados()
    processor.salvar_dados_tratados()

    # 2) Gera as 4 cartas (PDFs + PNGs em relatorios/)
    Cartas.gerar_todos_relatorios()

    # 3) Monta as respostas
    blocos = []
    por_chart = {d["chart"]: d for d in processor.dados_tratados}
    for chart in ("XR", "IMR"):
        if chart in por_chart:
            blocos.append(responder_variaveis(por_chart[chart]))

    # Q2: mesmo JSON para P e U. Usa o primeiro dataset de atributos disponível.
    ds_atrib = next((ds for ds in processor.datasets
                     if (ds.get("chart") or ds.get("Chart")) in ("P", "U")), None)
    if ds_atrib:
        dados_p, dados_u = processar_atributos_mesmo_json(processor, ds_atrib)
        blocos.append(responder_atributos(dados_p, dados_u))

    # 4) Response PDF (texto + imagens das cartas)
    report_dir = os.path.join(AQUI, "entrega_tmp", "report")
    data_dir = os.path.join(AQUI, "entrega_tmp", "data")
    code_dir = os.path.join(AQUI, "entrega_tmp", "code")
    for d in (report_dir, data_dir, code_dir):
        os.makedirs(d, exist_ok=True)

    imagens = [
        ("Carta X-R", os.path.join(rel_dir, "tmp_xr.png")),
        ("Carta I-MR", os.path.join(rel_dir, "tmp_imr.png")),
        ("Carta P", os.path.join(rel_dir, "tmp_p.png")),
        ("Carta U", os.path.join(rel_dir, "tmp_u.png")),
    ]
    response_pdf = os.path.join(report_dir, f"response_{matricula}.pdf")
    gerar_response_pdf(matricula, blocos, imagens, response_pdf)

    # 5) Copia código e dados para o layout de entrega
    for nome in ("gerar_entrega.py", "analise.py", "constantes.py"):
        shutil.copy2(os.path.join(AQUI, nome), code_dir)
    shutil.copytree(os.path.join(AQUI, "cartas_controle"),
                    os.path.join(code_dir, "cartas_controle"),
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(os.path.join(AQUI, "amostras", "data_processor.py"), code_dir)
    req = os.path.join(os.path.dirname(AQUI), "requirements.txt")
    if os.path.exists(req):
        shutil.copy2(req, code_dir)

    origem_dados = os.path.join(AQUI, "amostras", "banco_de_dados_amostras", arquivo_dados)
    if os.path.exists(origem_dados):
        # Renomeia para os nomes exigidos por tipo de carta.
        shutil.copy2(origem_dados, os.path.join(data_dir, "entrada.json"))
    for chart, nome in (("XR", "xr.json"), ("IMR", "mri.json")):
        if chart in por_chart:
            _salvar_json(por_chart[chart], os.path.join(data_dir, nome))
    if ds_atrib:
        _salvar_json(ds_atrib, os.path.join(data_dir, "atributos.json"))

    # 6) Zipa no formato <matricula>.zip
    destino_zip = os.path.join(AQUI, f"{matricula}.zip")
    _zipar(os.path.join(AQUI, "entrega_tmp"), destino_zip)
    shutil.rmtree(os.path.join(AQUI, "entrega_tmp"), ignore_errors=True)
    print(f"\n✓ ENTREGA GERADA: {destino_zip}")
    return True


def _salvar_json(obj, caminho):
    import json
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _zipar(pasta, destino_zip):
    with zipfile.ZipFile(destino_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for raiz, _, arquivos in os.walk(pasta):
            for a in arquivos:
                caminho = os.path.join(raiz, a)
                arc = os.path.relpath(caminho, pasta)
                z.write(caminho, arc)


if __name__ == "__main__":
    mat = sys.argv[1] if len(sys.argv) > 1 else "000000000"
    # Um único nome de arquivo (padrão) ou vários caminhos absolutos separados
    # (formato do professor: xr.json mri.json atributos.json).
    if len(sys.argv) > 3:
        arq = sys.argv[2:]          # lista de caminhos absolutos
    elif len(sys.argv) > 2:
        arq = sys.argv[2]           # arquivo único em banco_de_dados_amostras/
    else:
        arq = "dados_producao_total.json"
    ok = main(mat, arq)
    sys.exit(0 if ok else 1)
