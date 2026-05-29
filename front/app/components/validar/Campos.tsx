"use client";

export function Campo({
  label,
  value,
  onChange,
  tipo = "number",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  tipo?: "text" | "number";
}) {
  return (
    <div>
      <label className="block text-[11px] font-semibold tracking-widest text-fg-muted uppercase mb-1.5">
        {label}
      </label>
      <input
        type={tipo}
        value={value}
        step={tipo === "number" ? "any" : undefined}
        onChange={(e) => onChange(e.target.value)}
        className="w-full p-2 rounded-xl bg-surface border border-line text-fg placeholder:text-fg-muted font-mono text-sm focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent-soft transition"
      />
    </div>
  );
}

export function Stat({
  label,
  valor,
  dest = false,
}: {
  label: string;
  valor: string;
  dest?: boolean;
}) {
  return (
    <div className="bg-surface rounded-xl p-2.5 border border-line">
      <div className="text-[10px] font-semibold tracking-widest uppercase text-fg-muted">
        {label}
      </div>
      <div
        className={`font-mono mt-0.5 ${
          dest ? "text-accent text-base font-semibold" : "text-fg text-sm"
        }`}
      >
        {valor}
      </div>
    </div>
  );
}
