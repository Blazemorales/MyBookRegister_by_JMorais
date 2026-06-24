#!/usr/bin/env python
"""Script para debugar os caminhos do projeto."""

import os
import sys

# Adicionar o diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def debug_caminhos():
    print("\n" + "="*70)
    print("DEBUG DE CAMINHOS DO PROJETO")
    print("="*70 + "\n")
    
    # Caminho da raiz
    raiz = os.path.dirname(os.path.abspath(__file__))
    print(f"📁 Raiz do projeto: {raiz}\n")
    
    # Caminhos esperados
    print("📂 Estrutura esperada:")
    paths = {
        "Dados brutos": os.path.join(raiz, 'amostras', 'banco_de_dados_amostras'),
        "Dados tratados": os.path.join(raiz, 'banco_de_dados_tratados'),
        "Relatórios": os.path.join(raiz, 'relatorios'),
        "Data Processor": os.path.join(raiz, 'amostras', 'data_processor.py'),
        "Cartas": os.path.join(raiz, 'cartas_controle', 'Cartas.py'),
    }
    
    for nome, caminho in paths.items():
        existe = "✓" if os.path.exists(caminho) else "✗"
        print(f"  {existe} {nome}: {caminho}")
    
    # Verificar arquivo de dados
    print("\n📄 Verificando arquivo de dados:")
    arquivo_dados = os.path.join(raiz, 'amostras', 'banco_de_dados_amostras', 'dados_producao_total.json')
    if os.path.exists(arquivo_dados):
        tamanho = os.path.getsize(arquivo_dados) / 1024
        print(f"  ✓ dados_producao_total.json encontrado ({tamanho:.1f} KB)")
    else:
        print(f"  ✗ dados_producao_total.json NÃO encontrado")
    
    # Testar DataProcessor
    print("\n🔄 Testando DataProcessor:")
    try:
        from code.backend.CEP.amostras.data_processor import DataProcessor
        dp = DataProcessor()
        print(f"  ✓ DataProcessor importado")
        print(f"  ✓ Raiz do projeto (DataProcessor): {dp.raiz_projeto}")
        
        # Testar carregar
        if dp.carregar_dados_brutos('dados_producao_total.json'):
            print(f"  ✓ Dados carregados com sucesso")
            print(f"    Datasets carregados: {len(dp.datasets)}")
        else:
            print(f"  ✗ Erro ao carregar dados")
    except Exception as e:
        print(f"  ✗ Erro: {e}")
    
    # Testar Cartas
    print("\n📊 Testando Cartas:")
    try:
        from code.backend.CEP.cartas_controle.Cartas import Cartas
        caminho_dados, caminho_rel = Cartas.obter_caminhos()
        print(f"  ✓ Cartas importado")
        print(f"    Caminho dados tratados: {caminho_dados}")
        print(f"    Caminho relatórios: {caminho_rel}")
    except Exception as e:
        print(f"  ✗ Erro: {e}")
    
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    debug_caminhos()
