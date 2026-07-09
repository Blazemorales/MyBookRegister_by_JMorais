"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { io, type Socket } from "socket.io-client";

export interface Medicao {
  chart?: string;
  valor?: number;
  valores?: unknown;
  unidade?: string;
  amostra?: unknown;
  subgrupo?: unknown;
  label?: string;
  tag?: string;
  canal?: string;
  device_ts?: string | number | null;
  received_at: string;
}

export type SeveridadeAlerta = "critico" | "atencao" | "info";

export interface AlertaCep {
  regra: string;
  severidade: SeveridadeAlerta;
  mensagem: string;
  valor: number;
  media: number;
  desvio: number;
  canal: string;
  kalman: number | null;
  received_at: string;
}

export type StreamStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export interface DeviceStatus {
  canal: string;
  aceso: boolean;
  received_at: string;
}

export interface UseRelatorioStreamOptions {
  bufferSize?: number;
  socketUrl?: string;
  canal?: string;
  /** Pede ao servidor um replay dos últimos N pontos ao conectar. */
  replayN?: number;
}

export interface UseRelatorioStreamResult {
  status: StreamStatus;
  erro: string | null;
  ultimo: Medicao | null;
  buffer: Medicao[];
  alertas: AlertaCep[];
  /** Último `device_status` recebido (estado ao vivo do dispositivo, ex.: lâmpada ligada/desligada). */
  deviceStatus: DeviceStatus | null;
  limpar: () => void;
  limparAlertas: () => void;
}

const DEFAULT_SOCKET_URL =
  process.env.NEXT_PUBLIC_SOCKET_URL ?? "http://localhost:8000";
const DEFAULT_BUFFER_SIZE = 50;

export function useRelatorioStream(
  options: UseRelatorioStreamOptions = {},
): UseRelatorioStreamResult {
  const {
    bufferSize = DEFAULT_BUFFER_SIZE,
    socketUrl,
    canal,
    replayN,
  } = options;
  const url = socketUrl ?? DEFAULT_SOCKET_URL;

  const [status, setStatus] = useState<StreamStatus>("idle");
  const [erro, setErro] = useState<string | null>(null);
  const [buffer, setBuffer] = useState<Medicao[]>([]);
  const [alertas, setAlertas] = useState<AlertaCep[]>([]);
  const [deviceStatus, setDeviceStatus] = useState<DeviceStatus | null>(null);
  const socketRef = useRef<Socket | null>(null);

  const limpar = useCallback(() => setBuffer([]), []);
  const limparAlertas = useCallback(() => setAlertas([]), []);

  useEffect(() => {
    let cancelado = false;
    setStatus("connecting");
    setErro(null);

    async function conectar() {
      let token: string;
      try {
        const res = await fetch("/api/socket-token", { cache: "no-store" });
        if (!res.ok) {
          throw new Error(
            res.status === 401
              ? "sessão expirada — faça login novamente"
              : `falha ao obter token (HTTP ${res.status})`,
          );
        }
        const json = (await res.json()) as { token?: string };
        if (!json.token) throw new Error("token vazio");
        token = json.token;
      } catch (e) {
        if (cancelado) return;
        setStatus("error");
        setErro(e instanceof Error ? e.message : "falha ao obter token");
        return;
      }

      if (cancelado) return;

      const socket = io(url, {
        // Sem forçar "websocket": no Render o upgrade de WS falha (proxy
        // não repassa a conexão), mas o fallback padrão pra polling HTTP
        // funciona bem — forçar só websocket travava em timeout sempre.
        auth: { role: "frontend", token },
        reconnection: true,
        reconnectionAttempts: 10,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
      });
      socketRef.current = socket;

      socket.on("connect", () => {
        setStatus("connected");
        setErro(null);
        // Inscreve no canal e/ou pede replay. Servidor responderá com
        // eventos `relatorio_data` (do replay) antes do ack — o listener
        // abaixo já está montado, então tudo entra no buffer naturalmente.
        if (canal || (replayN && replayN > 0)) {
          socket.emit("subscribe_relatorio", {
            canal,
            replay_n: replayN,
          });
        }
      });

      socket.on("disconnect", (reason: string) => {
        setStatus("disconnected");
        if (reason === "io server disconnect") {
          setErro("desconectado pelo servidor");
        }
      });

      socket.on("connect_error", (err: Error) => {
        setStatus("error");
        setErro(err.message);
      });

      socket.on("relatorio_data", (data: Medicao) => {
        setBuffer((prev) => {
          const proximo = prev.length >= bufferSize ? prev.slice(1) : prev;
          return [...proximo, data];
        });
      });

      // Mantemos um buffer maior de alertas (50) porque cada um carrega
      // contexto valioso pro operador rastrear o que aconteceu.
      socket.on("alerta_cep", (alerta: AlertaCep) => {
        setAlertas((prev) => {
          const proximo = prev.length >= 50 ? prev.slice(1) : prev;
          return [...proximo, alerta];
        });
      });

      socket.on("device_status", (status: DeviceStatus) => {
        setDeviceStatus(status);
      });
    }

    conectar();

    return () => {
      cancelado = true;
      socketRef.current?.disconnect();
      socketRef.current = null;
    };
  }, [url, canal, bufferSize, replayN]);

  const ultimo = buffer.length > 0 ? buffer[buffer.length - 1] : null;

  return { status, erro, ultimo, buffer, alertas, deviceStatus, limpar, limparAlertas };
}
