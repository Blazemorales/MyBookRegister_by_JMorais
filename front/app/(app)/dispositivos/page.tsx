import Link from "next/link";

export default function DispositivosPage() {
  return (
    <>
      <section className="text-center pt-16 pb-10">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-[13px] text-fg-muted hover:text-fg transition-colors mb-6"
        >
          ← Menu
        </Link>
        <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight text-fg">
          Gerenciar dispositivos
        </h1>
        <p className="mt-3 text-lg text-fg-muted font-normal tracking-tight">
          Cadastre e administre seus dispositivos para leitura. Mantenha o controle e otimize suas análises.
        </p>
      </section>

      <div className="bg-surface border border-line rounded-3xl shadow-sm p-12 text-center">
        <p className="text-[15px] text-fg-muted">
          Em construção.
        </p>
      </div>
    </>
  );
}
