import json
import os
import random

def gerar_dados_teste_unico():
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    pasta_destino = os.path.join(diretorio_atual, 'banco_de_dados_amostras')

    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)

    # Lista única contendo os diferentes tipos de controle
    dados_globais = [
        {
            "Chart": "XR",
            "measurements": {str(i): [round(random.uniform(535, 545), 2) for _ in range(10)] for i in range(1, 11)},
            "Limite sup. Esp": 550,
            "Limite inf. Esp": 530
        },
        {
            "Chart": "P",
            "n_amostra": 100,
            "measurements": {str(i): [random.randint(0, 5)] for i in range(1, 11)}
        },
        {
            "Chart": "U",
            "n_amostra": 1,
            "measurements": {str(i): [random.randint(0, 8)] for i in range(1, 11)}
        }
    ]

    caminho_completo = os.path.join(pasta_destino, 'dados_producao_total.json')
    with open(caminho_completo, 'w', encoding='utf-8') as f:
        json.dump(dados_globais, f, indent=4, ensure_ascii=False)
            
    print(f"Sucesso! Arquivo único gerado em: {caminho_completo}")

if __name__ == "__main__":
    gerar_dados_teste_unico()