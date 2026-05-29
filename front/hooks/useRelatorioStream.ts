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

export type StreamStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export interface UseRelatorioStreamOptions {
  bufferSize?: number;
  socketUrl?: string;
  canal?: string;
}

export interface UseRelatorioStreamResult {
  status: StreamStatus;
  erro: string | null;
  ultimo: Medicao | null;
  buffer: Medicao[];
  limpar: () => void;
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
  } = options;
  const url = socketUrl ?? DEFAULT_SOCKET_URL;

  const [status, setStatus] = useState<StreamStatus>("idle");
  const [erro, setErro] = useState<string | null>(null);
  const [buffer, setBuffer] = useState<Medicao[]>([]);
  const socketRef = useRef<Socket | null>(null);

  const limpar = useCallback(() => setBuffer([]), []);

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
        transports: ["websocket"],
        auth: { role: "frontend", token },
        reconnection: true,
        reconnectionAttempts: 0,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
      });
      socketRef.current = socket;

      socket.on("connect", () => {
        setStatus("connected");
        setErro(null);
        if (canal) socket.emit("subscribe_relatorio", { canal });
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
    }

    conectar();

    return () => {
      cancelado = true;
      socketRef.current?.disconnect();
      socketRef.current = null;
    };
  }, [url, canal, bufferSize]);

  const ultimo = buffer.length > 0 ? buffer[buffer.length - 1] : null;

  return { status, erro, ultimo, buffer, limpar };
}
