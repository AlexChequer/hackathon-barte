import { Check, Copy } from "lucide-react";
import { useState } from "react";
import type { Rascunho } from "../api";

const PAPEL: Record<Rascunho["papel"], string> = {
  contraparte: "Contraparte",
  interno: "Interno",
  lojista: "Lojista",
};

/** Rascunhos de envio a terceiros: uma mensagem por destinatário, juntando as pendências dele (P36). */
export function Rascunhos({ rascunhos }: { rascunhos: Rascunho[] }) {
  if (rascunhos.length === 0) return null;
  const indisponivel = rascunhos.every((r) => r.status === "indisponivel");
  return (
    <section>
      <header className="mb-2 border-b border-linha-forte pb-2">
        <h2 className="text-[15px] font-semibold">
          Rascunhos de envio a terceiros
          <span className="ml-2 font-normal text-tinta-3">{rascunhos.length}</span>
        </h2>
      </header>
      <p className="mb-4 max-w-[68ch] text-sm text-tinta-2">
        Uma mensagem por destinatário, juntando as pendências dele. Os valores vêm do fechamento e foram
        conferidos; a IA só redigiu o texto, sem ver nomes, CNPJs nem valores. Revise antes de enviar.
      </p>
      {indisponivel && (
        <p className="mb-4 rounded-md border border-decisao/50 bg-decisao-fundo px-3 py-2 text-sm text-decisao-tinta">
          {rascunhos[0].aviso}
        </p>
      )}
      <ul className="space-y-4">
        {rascunhos.map((r) => (
          <Cartao key={r.chave} r={r} mostrarAviso={!indisponivel} />
        ))}
      </ul>
    </section>
  );
}

function Cartao({ r, mostrarAviso }: { r: Rascunho; mostrarAviso: boolean }) {
  const [copiado, setCopiado] = useState(false);
  const texto = [`Assunto: ${r.assunto}`, "", r.corpo, ...(r.anexo.length ? ["", ...r.anexo] : [])].join("\n");
  const copiar = async () => {
    await navigator.clipboard.writeText(texto);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 1500);
  };
  return (
    <li className="rounded-lg border border-linha bg-folha p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="font-medium">
          {r.destinatario}
          <span className="ml-2 text-xs font-normal text-tinta-3">{PAPEL[r.papel]}</span>
        </h3>
        {r.status === "gerado" && (
          <button onClick={copiar} className="flex items-center gap-1 text-xs text-tinta-2 hover:text-tinta">
            {copiado ? <Check size={14} /> : <Copy size={14} />} {copiado ? "Copiado" : "Copiar"}
          </button>
        )}
      </div>
      <p className="mt-1 font-mono text-xs text-tinta-3">{r.pendencias.join(" · ")}</p>
      {r.status === "gerado" ? (
        <div className="mt-3">
          <p className="text-sm font-medium">Assunto: {r.assunto}</p>
          <p className="mt-2 max-w-[78ch] whitespace-pre-wrap text-sm leading-relaxed text-tinta-2">{r.corpo}</p>
          {r.anexo.length > 0 && (
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer text-tinta-2">Lista anexada ({r.anexo.length} linhas)</summary>
              <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap font-mono text-xs text-tinta-3">
                {r.anexo.join("\n")}
              </pre>
            </details>
          )}
        </div>
      ) : (
        mostrarAviso && <p className="mt-3 text-sm text-decisao-tinta">{r.aviso}</p>
      )}
    </li>
  );
}
