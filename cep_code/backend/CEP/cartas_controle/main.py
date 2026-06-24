import sys
import os
import scipy.stats
import numpy as np

# --- CORREÇÃO DE PATH ---
raiz_projeto = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if raiz_projeto not in sys.path:
    sys.path.append(raiz_projeto)

from code.backend.CEP.cartas_controle.Cartas import Cartas
from code.backend.CEP.amostras.data_processor import DataProcessor


class Main:

    @staticmethod
    def processar_dados(arquivo_dados='dados_producao_total.json'):
        print("\n[ETAPA 1] Processando dados brutos...")
        processor = DataProcessor()

        if processor.processar_e_salvar(arquivo_dados):
            print("✓ Dados processados com sucesso!")
            return True
        else:
            print("✗ Erro ao processar dados")
            return False

    @staticmethod
    def gerar_relatorios():
        print("\n[ETAPA 2] Gerando relatórios...")

        if Cartas.gerar_todos_relatorios():
            print("✓ Relatórios gerados com sucesso!")
            return True
        else:
            print("✗ Erro ao gerar relatórios")
            return False

    @staticmethod
    def executar_completo(arquivo_dados='dados_producao_total.json'):
        print("\n" + "=" * 60)
        print("PIPELINE COMPLETO - PROCESSAMENTO E RELATÓRIOS")
        print("=" * 60)

        if Main.processar_dados(arquivo_dados):
            if Main.gerar_relatorios():
                print("\n" + "=" * 60)
                print("✓ PROCESSO FINALIZADO COM SUCESSO!")
                print("=" * 60 + "\n")
                return True

        print("\n" + "=" * 60)
        print("✗ ERRO NO PROCESSO")
        print("=" * 60 + "\n")
        return False

    @staticmethod
    def x():
        return Main.executar_completo()

    @staticmethod
    def r():
        dados = Cartas.carregar_dados_tratados()
        if dados:
            dados_r = next((d for d in dados if d.get("chart") == "XR"), None)
            if dados_r:
                return Cartas.carta_xr(dados_r)
        return False

    @staticmethod
    def p():
        dados = Cartas.carregar_dados_tratados()
        if dados:
            dados_p = next((d for d in dados if d.get("chart") == "P"), None)
            if dados_p:
                return Cartas.carta_p(dados_p)
        return Cartas.carta_p()

    @staticmethod
    def u():
        dados = Cartas.carregar_dados_tratados()
        if dados:
            dados_u = next((d for d in dados if d.get("chart") == "U"), None)
            if dados_u:
                return Cartas.carta_u(dados_u)
        return Cartas.carta_u()

    @staticmethod
    def imr():
        dados = Cartas.carregar_dados_tratados()
        if dados:
            dados_imr = next((d for d in dados if d.get("chart") == "IMR"), None)
            if dados_imr:
                return Cartas.carta_imr(dados_imr)
        return Cartas.carta_imr()

    # =========================
    # ✅ VALIDAÇÃO CORRIGIDA
    # =========================
    @staticmethod
    def validar_processo():
        print("\n[VALIDAÇÃO] Validando processo...")

        dados = Cartas.carregar_dados_tratados()
        if not dados:
            print("✗ Dados não encontrados.")
            return False

        while True:
            ponto = input("\nDigite um valor (ou 'sair'): ")

            if ponto.lower() == 'sair':
                break

            try:
                ponto = float(ponto)
            except ValueError:
                print("Valor inválido.")
                continue

            for chart in ["XR", "P", "U", "IMR"]:

                dados_chart = next(
                    (d for d in dados if d.get("chart") == chart),
                    None
                )

                if not dados_chart:
                    continue

                valores = dados_chart.get("values", [])
                if not valores:
                    continue

                media = np.mean(valores)
                sigma = np.std(valores)

                if sigma == 0:
                    print(f"[{chart}] ✗ Sigma = 0, impossível calcular.")
                    continue

                z = (ponto - media) / sigma
                p = 1 - scipy.stats.norm.cdf(z)
                cmc = 1 / p if p != 0 else float('inf')

                print(f"\n[{chart}]")
                print(f"Média: {media:.4f} | Sigma: {sigma:.4f}")
                print(f"Z: {z:.4f} | Probabilidade: {p:.6f}")
                print(f"CMC (ARL): {cmc:.2f}")

                # Interpretação estatística
                if p < 0.01:
                    print("→ Baixa probabilidade → possível erro tipo II")
                elif p > 0.1:
                    print("→ Alta probabilidade → possível erro tipo I")
                else:
                    print("→ Zona aceitável")

        print("\n✓ Validação concluída.")
        return True

    # =========================
    # VALIDADORES INDIVIDUAIS
    # =========================
    @staticmethod
    def validar_relatorio_xr():
        xr = Cartas.carta_xr()
        return xr.validar_processo() if xr else False

    @staticmethod
    def validar_relatorio_p():
        p = Cartas.carta_p()
        return p.validar_processo() if p else False

    @staticmethod
    def validar_relatorio_u():
        u = Cartas.carta_u()
        return u.validar_processo() if u else False

    @staticmethod
    def validar_relatorio_imr():
        imr = Cartas.carta_imr()
        return imr.validar_processo() if imr else False

    @staticmethod
    def main():
        Main.executar_completo()


if __name__ == "__main__":
    Main.main()