export const metadata = {
  title: "Configuração ausente",
  robots: { index: false, follow: false },
};

export default function AcessoNegado() {
  return (
    <main className="min-h-screen bg-canvas text-fg flex items-center justify-center p-8">
      <div className="max-w-md text-center space-y-5">
        <h1 className="text-4xl font-semibold tracking-tight">
          Configuração ausente
        </h1>
        <p className="text-[17px] text-fg-muted">
          O servidor ainda não tem as variáveis de ambiente necessárias para
          autenticação.
        </p>
        <p className="text-[13px] text-fg-muted">
          Defina <span className="font-mono text-fg">USERS</span> (formato{" "}
          <span className="font-mono text-fg">user1:senha1,user2:senha2</span>)
          e <span className="font-mono text-fg">AUTH_SECRET</span> (string
          aleatória) nas variáveis de ambiente da Vercel.
        </p>
      </div>
    </main>
  );
}
