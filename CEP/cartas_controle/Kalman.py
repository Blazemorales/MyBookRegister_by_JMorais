class Kalman:
    def __init__(self, processo_var, medida_var, estimativa_inicial, erro_inicial):
        self.__Q = processo_var  
        self.__R = medida_var    
        self.__x = estimativa_inicial
        self.__P = erro_inicial

        self.__historico_x = []
        self.__historico_P = []

    def filtrar(self, medida):
        # 1. Predição
        self.__P = self.__P + self.__Q
        # 2. Atualização
        K = self.__P / (self.__P + self.__R)
        self.__x = self.__x + K * (medida - self.__x)
        self.__P = (1 - K) * self.__P
        
        # Armazena histórico para diagnóstico
        self.__historico_x.append(self.__x)
        self.__historico_P.append(self.__P)
        
        return self.__x
    
    def resetar(self, estimativa_inicial, erro_inicial):
        """Reseta o filtro para uma nova amostra"""
        self.__x = estimativa_inicial
        self.__P = erro_inicial
        self.__historico_x = []
        self.__historico_P = []
    
    def obter_parametros(self):
        """Retorna os parâmetros do filtro"""
        return {
            'processo_var': self.__Q,
            'medida_var': self.__R,
            'estimativa': self.__x,
            'erro_estimativa': self.__P
        }
    
    def obter_ganho_kalman(self):
        """Retorna o ganho de Kalman atual"""
        return self.__P / (self.__P + self.__R)