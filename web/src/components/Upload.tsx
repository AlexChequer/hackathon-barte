import { AnimatePresence, motion } from "motion/react";
import { Check, FileUp, TriangleAlert, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

export interface Esperado {
  chave: string;
  padrao: string;
  obrigatorio: boolean;
  nome: string;
  descricao: string;
}

const IGNORADOS = ["00_LEIA-ME*"];
const casa = (nome: string, padrao: string) =>
  new RegExp(`^${padrao.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".")}$`).test(nome);

/** Mesma conferência do servidor (tarvo.loaders.validar_lote), para avisar antes de enviar. */
function conferir(arquivos: File[], esperados: Esperado[]) {
  const problemas: string[] = [];
  for (const f of arquivos)
    if (!esperados.some((e) => casa(f.name, e.padrao)) && !IGNORADOS.some((p) => casa(f.name, p)))
      problemas.push(`${f.name} não é um arquivo do fechamento`);
  const porEsperado = esperados.map((e) => ({ e, achados: arquivos.filter((f) => casa(f.name, e.padrao)) }));
  for (const { e, achados } of porEsperado) {
    if (e.obrigatorio && achados.length === 0) problemas.push(`falta o ${e.nome}`);
    if (e.obrigatorio && achados.length > 1) problemas.push(`mais de um ${e.nome}: ${achados.map((a) => a.name).join(", ")}`);
  }
  return { problemas, porEsperado };
}

export function Upload({
  aberto,
  aoFechar,
  aoEnviar,
}: {
  aberto: boolean;
  aoFechar: () => void;
  aoEnviar: (arquivos: FileList | File[]) => Promise<void>;
}) {
  const [esperados, setEsperados] = useState<Esperado[]>([]);
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [arrastando, setArrastando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erroServidor, setErroServidor] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch("/api/arquivos-esperados").then((r) => r.json()).then(setEsperados);
  }, []);
  useEffect(() => {
    if (!aberto) {
      setArquivos([]);
      setErroServidor(null);
    }
  }, [aberto]);

  const { problemas, porEsperado } = useMemo(() => conferir(arquivos, esperados), [arquivos, esperados]);
  const obrigatorios = esperados.filter((e) => e.obrigatorio);
  const pronto = arquivos.length > 0 && problemas.length === 0;
  const adicionar = (lista: FileList | null) => {
    if (!lista) return;
    const novos = Array.from(lista);
    setErroServidor(null);
    setArquivos((atuais) => [...atuais.filter((a) => !novos.some((n) => n.name === a.name)), ...novos]);
  };

  return (
    <AnimatePresence>
      {aberto && (
        <>
          <motion.div className="fixed inset-0 z-30 bg-tinta/10" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={aoFechar} />
          <motion.aside
            role="dialog"
            aria-label="Enviar arquivos do mês"
            className="fixed inset-y-0 right-0 z-40 flex w-full max-w-lg flex-col border-l border-linha bg-folha shadow-[0_8px_40px_-12px_oklch(0.24_0.02_255/0.25)]"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            <header className="flex items-start justify-between border-b border-linha px-6 pt-6 pb-5">
              <div>
                <h2 className="text-[15px] font-semibold">Enviar arquivos do mês</h2>
                <p className="mt-1 text-sm text-tinta-2">
                  Envie os <strong className="font-semibold text-tinta">{obrigatorios.length} arquivos</strong> abaixo, os mesmos
                  de todo mês. Sem um deles o fechamento não roda.
                </p>
              </div>
              <button onClick={aoFechar} aria-label="Fechar" className="rounded-md p-1.5 text-tinta-2 hover:bg-papel hover:text-tinta">
                <X size={18} />
              </button>
            </header>

            <div className="flex-1 space-y-5 overflow-y-auto px-6 py-5">
              <ol className="space-y-2">
                {porEsperado.map(({ e, achados }) => {
                  const ok = achados.length === 1 || (!e.obrigatorio && achados.length > 0);
                  const falta = e.obrigatorio && achados.length === 0 && arquivos.length > 0;
                  const repetido = e.obrigatorio && achados.length > 1;
                  return (
                    <li
                      key={e.chave}
                      className={`flex gap-3 rounded-md border px-3 py-2.5 text-sm transition-colors ${
                        falta || repetido ? "border-erro/40 bg-erro/5" : ok ? "border-linha bg-papel" : "border-linha"
                      }`}
                    >
                      <span className={`mt-0.5 shrink-0 ${ok ? "text-tinta" : falta || repetido ? "text-erro" : "text-tinta-3"}`}>
                        {ok ? <Check size={16} /> : falta || repetido ? <TriangleAlert size={16} /> : <FileUp size={16} />}
                      </span>
                      <span className="min-w-0">
                        <span className="font-medium">
                          {e.nome}
                          {!e.obrigatorio && <span className="ml-1.5 font-normal text-tinta-3">opcional</span>}
                        </span>
                        <span className="block text-tinta-2">{e.descricao}</span>
                        <span className="block truncate font-mono text-xs text-tinta-3">
                          {achados.length ? achados.map((a) => a.name).join(", ") : e.padrao}
                        </span>
                      </span>
                    </li>
                  );
                })}
              </ol>

              <button
                onClick={() => input.current?.click()}
                onDragOver={(ev) => {
                  ev.preventDefault();
                  setArrastando(true);
                }}
                onDragLeave={() => setArrastando(false)}
                onDrop={(ev) => {
                  ev.preventDefault();
                  setArrastando(false);
                  adicionar(ev.dataTransfer.files);
                }}
                className={`flex w-full flex-col items-center gap-1 rounded-lg border border-dashed py-6 text-sm transition-colors ${
                  arrastando ? "border-decisao bg-decisao-fundo text-decisao-tinta" : "border-linha-forte text-tinta-2 hover:border-tinta-3"
                }`}
              >
                <FileUp size={18} />
                Arraste os arquivos aqui ou clique para escolher
              </button>
              <input ref={input} type="file" multiple hidden onChange={(ev) => adicionar(ev.target.files)} />

              <AnimatePresence>
                {arquivos.length > 0 && problemas.length > 0 && (
                  <motion.div
                    role="alert"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="rounded-md border border-erro/40 bg-erro/5 px-4 py-3 text-sm text-erro"
                  >
                    <p className="font-semibold">Faça o upload dos arquivos corretos</p>
                    <ul className="mt-1 list-disc pl-5">
                      {problemas.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                  </motion.div>
                )}
              </AnimatePresence>
              {erroServidor && (
                <p role="alert" className="rounded-md border border-erro/40 bg-erro/5 px-4 py-3 text-sm text-erro">
                  {erroServidor}
                </p>
              )}
            </div>

            <footer className="flex items-center justify-between gap-3 border-t border-linha px-6 py-4">
              <div className="min-w-0 text-sm" aria-live="polite">
                {arquivos.length === 0 ? (
                  <span className="text-tinta-3">Nenhum arquivo escolhido</span>
                ) : problemas.length > 0 ? (
                  <span className="font-medium text-erro">Faça o upload dos arquivos corretos ({problemas.length} {problemas.length === 1 ? "problema" : "problemas"})</span>
                ) : (
                  <span className="flex items-center gap-1 text-tinta-2">
                    <Check size={15} /> Os {obrigatorios.length} arquivos estão certos ·{" "}
                    <button onClick={() => setArquivos([])} className="underline">limpar</button>
                  </span>
                )}
              </div>
              <button
                disabled={!pronto || enviando}
                onClick={async () => {
                  setEnviando(true);
                  setErroServidor(null);
                  try {
                    await aoEnviar(arquivos);
                  } catch (e) {
                    setErroServidor((e as Error).message);
                  } finally {
                    setEnviando(false);
                  }
                }}
                className="rounded-md bg-tinta px-4 py-2 text-sm font-medium text-folha transition-opacity disabled:opacity-40"
              >
                {enviando ? "Fechando o mês…" : "Fechar o mês com estes arquivos"}
              </button>
            </footer>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
