import { animate, AnimatePresence, motion, useMotionValue, useTransform } from "motion/react";
import { Check, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Linha } from "../api";
import { dinheiro } from "../format";

export interface AlvoRastro {
  id: string;
  titulo: string;
  valor: string;
}

const ARQUIVO: Record<string, string> = {
  orbe: "Relatório Orbe (01)",
  orbe_ajustes: "Ajustes tardios Orbe (06)",
  ponte: "Relatório Ponte (03)",
  aurora: "Extrato Aurora (05a)",
  meridiano: "Extrato Meridiano (05b)",
  taxas: "Planilha de taxas (02)",
};

/** "De onde vem esse número": as linhas de origem somam, à vista, até o valor exato. */
export function Rastro({ alvo, aoFechar }: { alvo: AlvoRastro | null; aoFechar: () => void }) {
  const [linhas, setLinhas] = useState<Linha[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const soma = useMotionValue(0);
  const somaTexto = useTransform(soma, (v) => dinheiro(v));
  const [fechou, setFechou] = useState(false);

  useEffect(() => {
    if (!alvo) return;
    setLinhas(null);
    setErro(null);
    setFechou(false);
    soma.set(0);
    api
      .rastro(alvo.id)
      .then((r) => {
        setLinhas(r.linhas);
        const total = r.linhas.reduce((t, l) => t + Number(l.valor), 0);
        animate(soma, total, { duration: 0.7, ease: [0.16, 1, 0.3, 1], onComplete: () => setFechou(true) });
      })
      .catch((e: Error) => setErro(e.message));
  }, [alvo, soma]);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && aoFechar();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [aoFechar]);

  const bate =
    linhas != null && alvo != null &&
    Math.round(linhas.reduce((t, l) => t + Number(l.valor), 0) * 100) === Math.round(Number(alvo.valor) * 100);

  return (
    <AnimatePresence>
      {alvo && (
        <>
          <motion.div
            className="fixed inset-0 z-30 bg-tinta/10"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={aoFechar}
          />
          <motion.aside
            role="dialog"
            aria-label={`Rastro de ${alvo.titulo}`}
            className="fixed inset-y-0 right-0 z-40 flex w-full max-w-xl flex-col border-l border-linha bg-folha shadow-[0_8px_40px_-12px_oklch(0.24_0.02_255/0.25)]"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            <header className="flex items-start justify-between gap-4 border-b border-linha px-6 pt-6 pb-5">
              <div className="min-w-0">
                <h2 className="text-[15px] font-semibold text-balance">De onde vem esse número</h2>
                <p className="mt-1 truncate text-sm text-tinta-2">{alvo.titulo}</p>
                <p className="mt-0.5 font-mono text-xs text-tinta-3">{alvo.id}</p>
              </div>
              <button
                onClick={aoFechar}
                className="rounded-md p-1.5 text-tinta-2 transition-colors hover:bg-papel hover:text-tinta"
                aria-label="Fechar"
              >
                <X size={18} />
              </button>
            </header>

            <div className="border-b border-linha bg-papel px-6 py-5">
              <div className="flex items-baseline justify-between">
                <span className="text-sm text-tinta-2">Soma das linhas de origem</span>
                <motion.span className="num text-2xl font-semibold">{somaTexto}</motion.span>
              </div>
              <div className="mt-2 flex items-center justify-between text-sm">
                <span className="text-tinta-2">Valor na saída</span>
                <span className="num font-medium">{dinheiro(alvo.valor)}</span>
              </div>
              <AnimatePresence>
                {fechou && (
                  <motion.p
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`mt-3 flex items-center gap-1.5 text-sm font-medium ${bate ? "text-tinta" : "text-erro"}`}
                  >
                    {bate ? <Check size={16} /> : <X size={16} />}
                    {bate
                      ? `Fecha no centavo, com ${linhas?.length} ${linhas?.length === 1 ? "linha" : "linhas"} de origem`
                      : "A soma não bate com o valor: verificar"}
                  </motion.p>
                )}
              </AnimatePresence>
            </div>

            <div className="flex-1 overflow-y-auto">
              {erro && <p className="px-6 py-5 text-sm text-erro">{erro}</p>}
              {!linhas && !erro && <p className="px-6 py-5 text-sm text-tinta-3">Buscando as linhas…</p>}
              {linhas && (
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-folha text-left text-xs text-tinta-3">
                    <tr className="border-b border-linha">
                      <th className="px-6 py-2.5 font-medium">Arquivo</th>
                      <th className="py-2.5 font-medium">Linha de origem</th>
                      <th className="px-6 py-2.5 text-right font-medium">Valor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {linhas.map((l, i) => (
                      <motion.tr
                        key={`${l.ref_origem}-${i}`}
                        className="border-b border-linha/70"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: Math.min(i * 0.012, 0.4), duration: 0.2 }}
                      >
                        <td className="px-6 py-2 text-tinta-2">{ARQUIVO[l.arquivo_origem ?? ""] ?? l.arquivo_origem}</td>
                        <td className="py-2 font-mono text-[13px]">{l.ref_origem}</td>
                        <td className="num px-6 py-2 text-right">{dinheiro(l.valor)}</td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
