export default function Loading() {
  return (
    <main className="min-h-screen bg-canvas text-fg flex items-center justify-center p-8">
      <div className="flex items-center gap-3 text-fg-muted">
        <span
          aria-hidden
          className="h-5 w-5 rounded-full border-2 border-fg-muted/30 border-t-accent animate-spin"
        />
        <span className="text-[15px]">Carregando…</span>
      </div>
    </main>
  );
}
