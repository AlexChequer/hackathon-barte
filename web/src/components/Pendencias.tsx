import { AnimatePresence, motion } from "motion/react";
import { ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import type { Fechamento, Linha, SinalAberto } from "../api";
import { ARQUIVO, cnpj, tipoPendencia } from "../format";
import { Valor } from "./Valor";

const ORDEM = ["Financeiro", "Financeiro + Comercial", "Comercial"];
const PAPEL: Record<string, string> = {
  Financeiro: "Helena decide",
  "Financeiro + Comercial": "Helena com o comercial",
  Comercial: "Comercial decide antes",
};

interface Props {
  fechamento: Fechamento;
  sinais: SinalAberto[];
  aoRegistrarCondicao: (sinal?: SinalAberto) => void;
  aoResolverSinal: (sinal: SinalAberto) => void;
  aoVerCondicoes: () => void;
}

export function Pendencias({ fechamento, sinais, aoRegistrarCondicao, aoResolverSinal, aoVerCondicoes }: Props) {
  const pend = fechamento.tabelas.pendencias;
  const grupos = useMemo(() => {
    const por: Record<string, Linha[]> = {};
    for (const p of pend) (por[p.quem_decide ?? "—"] ??= []).push(p);
    return Object.entries(por).sort(([a], [b]) => (ORDEM.indexOf(a) + 99) % 99 - (ORDEM.indexOf(b) + 99) % 99);
  }, [pend]);
  const [aberta, setAberta] = useState<string | null>(null);
  const nomes = useMemo(() => nomesPorCnpj(fechamento), [fechamento]);

  if (pend.length === 0) {
    return (
      <div className="max-w-xl py-16">
        <h2 className="text-xl font-semibold">Nenhuma pendência</h2>
        <p className="mt-2 text-tinta-2">Tudo o que veio nos arquivos foi decidido por regra. O mês pode ser liberado.</p>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <p className="max-w-[68ch] text-tinta-2">
        O mês fecha quando esta fila zera. Cada item diz o que aconteceu, quanto está em jogo e quem decide. Clique
        em um valor para ver as linhas de origem.
      </p>
      {grupos.map(([quem, itens]) => (
        <section key={quem}>
          <header className="mb-2 flex items-baseline justify-between border-b border-linha-forte pb-2">
            <h2 className="text-[15px] font-semibold">
              {PAPEL[quem] ?? quem}
              <span className="ml-2 font-normal text-tinta-3">{itens.length}</span>
            </h2>
            <span className="text-xs text-tinta-3">quem decide: {quem}</span>
          </header>
          <ul>
            {itens.map((p) => {
              const id = p.id_saida as string;
              const sinal = sinais.find((s) => s.id_saida === id);
              const expandida = aberta === id;
              return (
                <li key={id} className="border-b border-linha">
                  <div className="grid grid-cols-[1.25rem_1fr_auto] items-center gap-3 py-3">
                    <button
                      onClick={() => setAberta(expandida ? null : id)}
                      aria-expanded={expandida}
                      aria-label={expandida ? "Recolher" : "Ver detalhes"}
                      className="text-tinta-3 hover:text-tinta"
                    >
                      <motion.span animate={{ rotate: expandida ? 90 : 0 }} transition={{ duration: 0.15 }} className="block">
                        <ChevronRight size={16} />
                      </motion.span>
                    </button>
                    <button onClick={() => setAberta(expandida ? null : id)} className="min-w-0 overflow-hidden text-left">
                      <span className="block font-medium sm:inline">{tipoPendencia(p.tipo)}</span>
                      <span className="block truncate text-sm text-tinta-2 sm:ml-2 sm:inline">{rotulo(p, nomes)}</span>
                    </button>
                    <Valor id={id} valor={p.valor_brl} titulo={`${tipoPendencia(p.tipo)} · ${rotulo(p, nomes)}`} />
                  </div>
                  <AnimatePresence initial={false}>
                    {expandida && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                        className="overflow-hidden"
                      >
                        <div className="pb-4 pl-8">
                          <p className="max-w-[72ch] text-sm leading-relaxed text-tinta-2">{p.motivo}</p>
                          {p.proximo_passo && (
                            <p className="mt-3 max-w-[72ch] border-l-2 border-decisao pl-3 text-sm leading-relaxed text-tinta">
                              <span className="font-medium text-decisao-tinta">Próximo passo: </span>
                              {p.proximo_passo}
                            </p>
                          )}
                          <p className="mt-2 font-mono text-xs text-tinta-3">{id}</p>
                          <Acoes
                            pendencia={p}
                            sinal={sinal}
                            aoRegistrarCondicao={aoRegistrarCondicao}
                            aoResolverSinal={aoResolverSinal}
                            aoVerCondicoes={aoVerCondicoes}
                          />
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}

/** Nome de checkout primeiro (o da Ponte vem truncado e em caixa alta). */
export function nomesPorCnpj(f: Fechamento): Record<string, string> {
  const nomes: Record<string, string> = {};
  for (const linha of ["REMESSA", "CHECKOUT"])
    for (const c of f.tabelas.comissoes) if (c.linha_negocio === linha && c.cnpj && c.lojista) nomes[c.cnpj] = c.lojista;
  return nomes;
}

function rotulo(p: Linha, nomes: Record<string, string>): string {
  const ref = p.ref_origem ?? "";
  const id = p.id_saida ?? "";
  if (p.tipo === "FRENTE_BLOQUEADA") return `falta ${ref.split("|").map((a) => ARQUIVO[a] ?? a).join(", ")}`;
  if (/^\d{14}$/.test(ref)) return nomes[ref] ?? (p.motivo ?? "").split(/[:(]/)[0].trim() ?? cnpj(ref);
  if (ref === "relatorio_ponte") return "Ponte Câmbio, relatório do mês";
  const banco = id.match(/^EX-PN-(AURORA|MERIDIANO)-/)?.[1];
  if (banco) return `${banco === "AURORA" ? "Aurora" : "Meridiano"} · linha ${ref}`;
  if (/^L\d+$/.test(ref)) return `Planilha de taxas · ${ref}`;
  return ref;
}

function Acoes({
  pendencia,
  sinal,
  aoRegistrarCondicao,
  aoResolverSinal,
  aoVerCondicoes,
}: {
  pendencia: Linha;
  sinal?: SinalAberto;
  aoRegistrarCondicao: (s?: SinalAberto) => void;
  aoResolverSinal: (s: SinalAberto) => void;
  aoVerCondicoes: () => void;
}) {
  const botao = "rounded-md border px-3 py-1.5 text-sm font-medium transition-colors";
  if (sinal) {
    return (
      <div className="mt-4 flex flex-wrap gap-2">
        <button onClick={() => aoRegistrarCondicao(sinal)} className={`${botao} border-decisao bg-decisao-fundo text-decisao-tinta hover:bg-decisao/20`}>
          Muda a taxa: registrar condição
        </button>
        <button onClick={() => aoResolverSinal(sinal)} className={`${botao} border-linha-forte hover:bg-papel`}>
          Não muda a taxa
        </button>
      </div>
    );
  }
  if (pendencia.tipo === "CONDICAO_NAO_INFORMADA_ORBE") {
    return (
      <div className="mt-4">
        <button onClick={aoVerCondicoes} className={`${botao} border-linha-forte hover:bg-papel`}>
          Ver a condição comercial registrada
        </button>
      </div>
    );
  }
  return null;
}

