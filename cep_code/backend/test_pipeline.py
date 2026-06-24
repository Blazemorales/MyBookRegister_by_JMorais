#!/usr/bin/env python
"""Script para testar o pipeline completo de processamento e geração de relatórios."""

import sys
import os

# Adicionar o diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("\n" + "="*70)
    print("TESTE COMPLETO - PROCESSAMENTO E GERAÇÃO DE CARTAS DE CONTROLE")
    print("="*70 + "\n")
    
    # Importar após adicionar ao path
    from code.backend.CEP.cartas_controle.main import Main
    
    # Executar pipeline completo
    sucesso = Main.executar_completo('dados_producao_total.json')
    
    if sucesso:
        print("\n✓ Teste concluído com sucesso!")
        print("\nArquivos gerados:")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        relatorios_dir = os.path.join(base_dir, 'relatorios')
        
        if os.path.exists(relatorios_dir):
            pdfs = [f for f in os.listdir(relatorios_dir) if f.endswith('.pdf')]
            for pdf in pdfs:
                caminho_completo = os.path.join(relatorios_dir, pdf)
                tamanho = os.path.getsize(caminho_completo) / 1024  # KB
                print(f"  - {pdf} ({tamanho:.1f} KB)")
        
        return 0
    else:
        print("\n✗ Teste falhou!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
