import Link from "next/link";

export default function MenuPage() {
  return (
    <>
      <section className="text-center pt-20 pb-14">
        <h1 className="text-5xl sm:text-6xl font-semibold tracking-tight text-fg">
          MyBookRegister by J.Morais
        </h1>
        <p className="mt-4 text-xl sm:text-2xl text-fg-muted font-normal tracking-tight">
          Monitore e gerencie sua evolução de forma simples e eficiente.
        </p>
        <p className="mt-2 text-[15px] text-fg-muted">
          Selecione uma ferramenta.
        </p>
      </section>

      <div className="grid grid-cols-1 sm:grid-cols-1 gap-4 max-w-3xl mx-auto">
        <MenuCard
          href="/dispositivos"
          title="Gerenciar dispositivos"
          description="Cadastre e administre os dispositivos para leitura."
        />
        <MenuCard
          href="/cep"
          title="Minhas Estatísticas"
          description="Visualizar sua evolução e desempenho ao longo do tempo, podendo calibrar e validar resultados."
        />
        <MenuCard
          href="/ao-vivo"
          title="Receber em tempo real"
          description="Acompanhe as medições do dispositivo conforme chegam, sem atualizar a página."
        />
      </div>
    </>
  );
}

function MenuCard({
  href,
  title,
  description,
}: {
  href: string;
  title: string;
  description: string;
}) {
  return (
    <Link
      href={href}
      className="group bg-surface border border-line rounded-3xl shadow-sm p-6 hover:border-accent/40 hover:shadow-md transition-all"
    >
      <h2 className="text-[19px] font-semibold tracking-tight text-fg group-hover:text-accent transition-colors">
        {title}
      </h2>
      <p className="mt-2 text-[14px] text-fg-muted leading-relaxed">
        {description}
      </p>
      <span className="mt-4 inline-flex items-center gap-1 text-[13px] text-accent font-medium">
        Abrir
        <span
          aria-hidden
          className="transition-transform group-hover:translate-x-0.5"
        >
          →
        </span>
      </span>
    </Link>
  );
}
