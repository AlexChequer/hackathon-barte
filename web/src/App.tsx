import { AnimatePresence, motion, MotionConfig } from "motion/react";
import { TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type Fechamento, type SinalAberto } from "./api";
import { Condicoes } from "./components/Condicoes";
import { Pendencias } from "./components/Pendencias";
import { Rastro, type AlvoRastro } from "./components/Rastro";
import { Arquivos } from "./components/Upload";
import { Divergencias, Lancamentos, Numeros, Rastro as RastroTabela } from "./components/Tabelas";
import { RastroContext } from "./components/Valor";
import { ARQUIVO, FRENTE } from "./format";

type Tela = "arquivos" | "pendencias" | "numeros" | "divergencias" | "lancamentos" | "rastro" | "condicoes";

export default function App() {
  const [f, setF] = useState<Fechamento | null>(null);
  const [sinais, setSinais] = useState<SinalAberto[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<string | null>("Carregando o fechamento…");
  const [tela, setTela] = useState<Tela>("arquivos");
  const [alvo, setAlvo] = useState<AlvoRastro | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [sinalForm, setSinalForm] = useState<SinalAberto | null>(null);

  const aplicar = useCallback(async (novo: Fechamento) => {
    setF(novo);
    setSinais(await api.sinais().catch(() => []));
  }, []);

  const executar = useCallback(
    async (rotulo: string, acao: () => Promise<Fechamento>) => {
      setOcupado(rotulo);
      setErro(null);
      try {
        await aplicar(await acao());
      } catch (e) {
        setErro((e as Error).message);
      } finally {
        setOcupado(null);
      }
    },
    [aplicar],
  );

  useEffect(() => {
    executar("Carregando o fechamento…", api.fechamento);
  }, [executar]);

  useEffect(() => {
    if (!aviso) return;
    const t = setTimeout(() => setAviso(null), 5000);
    return () => clearTimeout(t);
  }, [aviso]);

  const pend = f?.tabelas.pendencias ?? [];
  const nav: [Tela, string, number | null][] = [
    ["arquivos", "Arquivos e fechamento", null],
    ["pendencias", "Pendências", pend.length],
    ["numeros", "Comissões e notas", null],
    ["divergencias", "Divergências", f?.tabelas.divergencias.length ?? null],
    ["lancamentos", "Lançamentos", f?.tabelas.lancamentos.length ?? null],
    ["rastro", "Rastro", null],
    ["condicoes", "Condições comerciais", null],
  ];

  return (
    <MotionConfig reducedMotion="user">
      <RastroContext.Provider value={setAlvo}>
        <div className="min-h-screen overflow-x-hidden">
          <header className="sticky top-0 z-20 border-b border-linha bg-papel/95 backdrop-blur-sm">
            <div className="mx-auto flex max-w-[1400px] items-center px-6 py-4">
              <h1 className="text-3xl font-bold tracking-tight">Tarvo</h1>
            </div>
          </header>

          <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-8 px-4 py-6 sm:px-6 sm:py-8 md:grid-cols-[13rem_1fr]">
            <nav aria-label="Seções" className="min-w-0 md:sticky md:top-24 md:self-start">
              <ul className="flex gap-1 overflow-x-auto md:flex-col md:overflow-visible">
                {nav.map(([id, nome, n]) => (
                  <li key={id}>
                    <button
                      onClick={() => setTela(id)}
                      aria-current={tela === id ? "page" : undefined}
                      className={`relative flex w-full items-center justify-between gap-3 whitespace-nowrap rounded-md px-3 py-2 text-left text-sm transition-colors ${
                        tela === id ? "font-medium text-tinta" : "text-tinta-2 hover:bg-folha hover:text-tinta"
                      }`}
                    >
                      {tela === id && (
                        <motion.span layoutId="nav-ativa" className="absolute inset-0 -z-10 rounded-md bg-folha shadow-[0_1px_3px_oklch(0.24_0.02_255/0.08)]" transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }} />
                      )}
                      {nome}
                      {n != null && (
                        <span className={`num text-xs ${id === "pendencias" && n > 0 ? "rounded-full bg-decisao-fundo px-1.5 py-0.5 font-semibold text-decisao-tinta" : "text-tinta-3"}`}>
                          {n}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </nav>

            <main className="min-w-0">
              {erro && (
                <div role="alert" className="mb-6 flex gap-2 rounded-lg border border-erro/30 bg-folha px-4 py-3 text-sm text-erro">
                  <TriangleAlert size={16} className="mt-0.5 shrink-0" /> <span>{erro}</span>
                </div>
              )}
              {f && f.bloqueios.length > 0 && (
                <div role="status" className="mb-6 rounded-lg border border-decisao/50 bg-decisao-fundo px-4 py-3 text-sm text-decisao-tinta">
                  <p className="flex items-center gap-1.5 font-semibold">
                    <TriangleAlert size={15} /> Fechamento parcial: faltaram arquivos ou algum mudou de layout
                  </p>
                  <ul className="mt-1 space-y-0.5">
                    {f.bloqueios.map((b) => (
                      <li key={b.frente}>
                        <strong className="font-medium">{FRENTE[b.frente]}</strong> {b.parcial ? "fechou em parte" : "não fechou"}:{" "}
                        {b.motivo_layout ? (
                          <span className="font-mono text-xs">{b.motivo_layout}</span>
                        ) : (
                          <>falta {b.faltando.map((a) => ARQUIVO[a]).join(", ")}. Envie e feche de novo.</>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {tela === "arquivos" ? (
                <AnimatePresence mode="wait">
                  <motion.div key="arquivos" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }}>
                    <h2 className="mb-6 text-2xl font-semibold tracking-tight text-balance">Arquivos e fechamento</h2>
                    <Arquivos
                      temFechamento={Boolean(f)}
                      ocupado={ocupado}
                      aoEnviar={async (arquivos) => {
                        const novo = await api.enviarArquivos(arquivos);
                        await aplicar(novo);
                        setAviso(`Mês fechado com os arquivos enviados: ${novo.tabelas.pendencias.length} pendências.`);
                        setTela("pendencias");
                      }}
                      aoFecharDeNovo={async () => {
                        await executar("Fechando o mês de novo…", api.fechar);
                        setTela("pendencias");
                      }}
                    />
                  </motion.div>
                </AnimatePresence>
              ) : !f ? (
                <p className="py-16 text-tinta-3">{ocupado ?? "Sem fechamento. Envie os arquivos do mês para começar."}</p>
              ) : (
                <AnimatePresence mode="wait">
                  <motion.div key={tela} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }}>
                    <h2 className="mb-6 text-2xl font-semibold tracking-tight text-balance">
                      {tela === "pendencias" ? (
                        <>
                          {pend.length} {pend.length === 1 ? "pendência" : "pendências"}{" "}
                          <span className="font-normal text-tinta-3">para fechar o mês</span>
                        </>
                      ) : (
                        nav.find(([id]) => id === tela)?.[1]
                      )}
                    </h2>
                    {tela === "pendencias" && (
                      <Pendencias
                        fechamento={f}
                        sinais={sinais}
                        aoVerCondicoes={() => setTela("condicoes")}
                        aoRegistrarCondicao={(s) => {
                          setSinalForm(s ?? null);
                          setTela("condicoes");
                        }}
                        aoResolverSinal={(s) =>
                          executar("Registrando a decisão…", async () => {
                            const r = await api.resolverSinal({ cnpj: s.cnpj, texto: s.texto, fonte: `pendência ${s.id_saida}`, registrado_por: "Helena" });
                            setAviso("Anotação marcada como sem efeito na taxa. Não volta nos próximos meses.");
                            return r.fechamento;
                          })
                        }
                      />
                    )}
                    {tela === "numeros" && <Numeros f={f} />}
                    {tela === "divergencias" && <Divergencias f={f} />}
                    {tela === "lancamentos" && <Lancamentos f={f} />}
                    {tela === "rastro" && <RastroTabela f={f} />}
                    {tela === "condicoes" && (
                      <Condicoes
                        fechamento={f}
                        competencia={f.competencia}
                        sinalInicial={sinalForm}
                        aoGravar={async (msg) => {
                          setSinalForm(null);
                          setAviso(msg);
                          await executar("Atualizando…", api.fechamento);
                        }}
                      />
                    )}
                  </motion.div>
                </AnimatePresence>
              )}
            </main>
          </div>

          <Rastro alvo={alvo} aoFechar={() => setAlvo(null)} />

          <AnimatePresence>
            {aviso && (
              <motion.div
                role="status"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 12 }}
                transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-tinta px-4 py-2.5 text-sm text-folha shadow-[0_8px_24px_-8px_oklch(0.24_0.02_255/0.4)]"
              >
                {aviso}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </RastroContext.Provider>
    </MotionConfig>
  );
}
