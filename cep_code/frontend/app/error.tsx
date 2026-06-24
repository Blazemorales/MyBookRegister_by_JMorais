"use client";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="min-h-screen bg-canvas text-fg flex items-center justify-center p-8">
      <div className="max-w-md text-center space-y-5">
        <h1 className="text-4xl font-semibold tracking-tight">
          Algo deu errado
        </h1>
        <p className="text-[17px] text-fg-muted">
          Tente novamente. Se o problema persistir, recarregue a página.
        </p>
        <button
          onClick={reset}
          className="px-5 py-2 rounded-full bg-accent hover:bg-accent-hover text-white font-medium tracking-tight transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    </main>
  );
}
