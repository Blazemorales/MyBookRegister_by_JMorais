import os
from flask import Flask, send_file, jsonify
import matplotlib

# Configuração para servidores Headless (sem interface gráfica)
matplotlib.use('Agg') 

app = Flask(__name__)

# Caminhos absolutos baseados na localização deste arquivo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_RELATORIOS = os.path.join(BASE_DIR, 'relatorios')
PASTA_RESULTADOS = os.path.join(BASE_DIR, 'amostras', 'resultados')

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "projeto": "CPE - Controle Estatístico de Processo",
        "endpoints": {
            "processar": "/processar",
            "relatorio_xr": "/relatorio/xr",
            "relatorio_p": "/relatorio/p",
            "relatorio_u": "/relatorio/u",
            "relatorio_imr": "/relatorio/imr",
            "validar_processo": "/validarprocesso",
            "resultados_cep": "/results/cep/<chart>"
        }
    })

@app.route('/processar', methods=['GET'])
def processar():
    """Processa dados brutos e gera todos os relatórios."""
    try:
        from CEP.cartas_controle.main import Main
        if Main.executar_completo():
            return jsonify({"status": "sucesso", "message": "Dados processados e relatórios gerados"}), 200
        else:
            return jsonify({"status": "erro", "message": "Falha ao processar dados"}), 500
    except Exception as e:
        return jsonify({"status": "erro", "message": str(e)}), 500

@app.route('/relatorio/xr', methods=['GET'])
def relatorio_xr():
    """Retorna relatório XR."""
    try:
        from CEP.cartas_controle.main import Main
        Main.x()
        caminho_pdf = os.path.join(PASTA_RELATORIOS, "relatorio_XR.pdf")
        if os.path.exists(caminho_pdf):
            return send_file(caminho_pdf, as_attachment=True)
        return jsonify({"error": "PDF XR não encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/relatorio/p', methods=['GET'])
def relatorio_p():
    """Retorna relatório P."""
    try:
        # Assegura que os dados tratados existam gerando o índice se necessário
        from CEP.cartas_controle.main import Main
        Main.processar_dados()
        # Tenta gerar o relatório P
        Main.p()
        caminho_pdf = os.path.join(PASTA_RELATORIOS, "relatorio_P.pdf")
        if os.path.exists(caminho_pdf):
            return send_file(caminho_pdf, as_attachment=True)
        return jsonify({"error": "PDF P não encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/relatorio/u', methods=['GET'])
def relatorio_u():
    """Retorna relatório U."""
    try:
        # Assegura que os dados tratados existam gerando o índice se necessário
        from CEP.cartas_controle.main import Main
        Main.processar_dados()
        # Tenta gerar o relatório U
        Main.u()
        caminho_pdf = os.path.join(PASTA_RELATORIOS, "relatorio_U.pdf")
        if os.path.exists(caminho_pdf):
            return send_file(caminho_pdf, as_attachment=True)
        return jsonify({"error": "PDF U não encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/relatorio/imr', methods=['GET'])
def relatorio_imr():
    """Retorna relatório IMR."""
    try:
        caminho_pdf = os.path.join(PASTA_RELATORIOS, "relatorio_IMR.pdf")
        if os.path.exists(caminho_pdf):
            return send_file(caminho_pdf, as_attachment=True)
        return jsonify({"error": "PDF IMR não encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/results/cep/<chart>', methods=['GET'])
def resultado_cep(chart):
    """Retorna o JSON tratado da carta de controle solicitada."""
    nome = chart.lower().strip()
    nomes_validos = {'xr', 'p', 'u', 'imr'}
    if nome not in nomes_validos:
        return jsonify({
            "error": f"Carta '{chart}' inválida.",
            "validas": sorted(nomes_validos)
        }), 400

    caminho_json = os.path.join(PASTA_RESULTADOS, f"{nome}.json")
    if not os.path.exists(caminho_json):
        return jsonify({
            "error": f"Resultado para '{nome}' não encontrado. Execute /processar primeiro."
        }), 404

    return send_file(caminho_json, mimetype='application/json')

@app.route('/validarprocesso', methods=['GET'])
def validar_processo():
    """Valida se o processo de geração de relatórios está funcionando corretamente."""
    try:
        from CEP.cartas_controle.main import Main
        if Main.validar_processo():
            return jsonify({"status": "sucesso", "message": "Processo de geração de relatórios validado com sucesso"}), 200
        else:
            return jsonify({"status": "erro", "message": "Falha na validação do processo de geração de relatórios"}), 500
    except Exception as e:
        return jsonify({"status": "erro", "message": str(e)}), 500
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)