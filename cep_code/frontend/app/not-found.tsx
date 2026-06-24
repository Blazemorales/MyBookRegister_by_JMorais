import Link from "next/link";

export default function NotFound() {
  return (
    <main className="min-h-screen bg-canvas text-fg flex items-center justify-center p-8">
      <div className="max-w-md text-center space-y-5">
        <h1 className="text-5xl font-semibold tracking-tight">404</h1>
        <p className="text-[17px] text-fg-muted">
          Não encontramos essa página.
        </p>
        <Link
          href="/"
          className="inline-block px-5 py-2 rounded-full bg-accent hover:bg-accent-hover text-white font-medium tracking-tight transition-colors"
        >
          Voltar ao menu
        </Link>
      </div>
    </main>
  );
}
