import { createContext, useContext } from "react";
import { dinheiro } from "../format";
import type { AlvoRastro } from "./Rastro";

export const RastroContext = createContext<(alvo: AlvoRastro) => void>(() => {});

/** Todo valor de saída é clicável e abre o rastro dele. */
export function Valor({ id, valor, titulo, forte }: { id: string; valor: string | null; titulo: string; forte?: boolean }) {
  const abrir = useContext(RastroContext);
  return (
    <button
      onClick={() => valor != null && abrir({ id, valor, titulo })}
      className={`num rounded px-1 -mx-1 text-right underline decoration-linha-forte decoration-dotted underline-offset-4 transition-colors hover:bg-decisao-fundo hover:decoration-decisao ${forte ? "font-semibold" : ""}`}
      title="Ver de onde vem esse número"
    >
      {dinheiro(valor)}
    </button>
  );
}
