import { AnimatePresence, motion, MotionConfig } from "motion/react";
import { Check, FileUp, RefreshCw, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type Fechamento, type SinalAberto } from "./api";
import { Condicoes } from "./components/Condicoes";
import { Pendencias } from "./components/Pendencias";
import { Rastro, type AlvoRastro } from "./components/Rastro";
import { Upload } from "./components/Upload";
import { Divergencias, Lancamentos, Numeros } from "./components/Tabelas";
import { RastroContext } from "./components/Valor";
import { competencia as nomeCompetencia } from "./format";

type Tela = "pendencias" | "numeros" | "divergencias" | "lancamentos" | "condicoes";

export default function App() {
  const [f, setF] = useState<Fechamento | null>(null);
  const [sinais, setSinais] = useState<SinalAberto[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<string | null>("Fechando o mês…");
  const [tela, setTela] = useState<Tela>("pendencias");
  const [alvo, setAlvo] = useState<AlvoRastro | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [sinalForm, setSinalForm] = useState<SinalAberto | null>(null);
  const [uploadAberto, setUploadAberto] = useState(false);

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
    executar("Fechando o mês…", api.fechamento);
  }, [executar]);

  useEffect(() => {
    if (!aviso) return;
    const t = setTimeout(() => setAviso(null), 5000);
    return () => clearTimeout(t);
  }, [aviso]);

  const pend = f?.tabelas.pendencias ?? [];
  const nav: [Tela, string, number | null][] = [
    ["pendencias", "Pendências", pend.length],
    ["numeros", "Comissões e notas", null],
    ["divergencias", "Divergências", f?.tabelas.divergencias.length ?? null],
    ["lancamentos", "Lançamentos", f?.tabelas.lancamentos.length ?? null],
    ["condicoes", "Condições comerciais", null],
  ];

  return (
    <MotionConfig reducedMotion="user">
      <RastroContext.Provider value={setAlvo}>
        <div className="min-h-screen overflow-x-hidden">
          <header className="sticky top-0 z-20 border-b border-linha bg-papel/95 backdrop-blur-sm">
            <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-6 gap-y-3 px-6 py-4">
              <div className="mr-auto">
                <h1 className="text-[17px] font-semibold tracking-tight">
                  Fechamento {f ? <span className="text-tinta-2 font-normal">de {nomeCompetencia(f.competencia)}</span> : null}
                </h1>
                {f && (
                  <p className="mt-0.5 text-xs text-tinta-3">
                    {f.arquivos.length} arquivos lidos · regras {f.regras_versao} · execução #{f.execucao_id} em {f.duracao_s?.toFixed(2)} s
                  </p>
                )}
              </div>
              {f && <Status f={f} />}
              <div className="flex gap-2">
                <button
                  onClick={() => setUploadAberto(true)}
                  className="flex items-center gap-1.5 rounded-md border border-linha-forte bg-folha px-3 py-1.5 text-sm font-medium hover:bg-papel"
                >
                  <FileUp size={15} /> Enviar arquivos do mês
                </button>
                <button
                  onClick={() => executar("Fechando o mês de novo…", api.fechar)}
                  disabled={Boolean(ocupado)}
                  className="flex items-center gap-1.5 rounded-md bg-tinta px-3 py-1.5 text-sm font-medium text-folha disabled:opacity-60"
                >
                  <RefreshCw size={15} className={ocupado ? "animate-spin" : ""} /> Fechar de novo
                </button>
              </div>
            </div>
          </header>

          <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-8 px-4 py-6 sm:px-6 sm:py-8 md:grid-cols-[13rem_1fr]">
            <nav aria-label="Seções" className="min-w-0 md:sticky md:top-28 md:self-start">
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
              {!f ? (
                <p className="py-16 text-tinta-3">{ocupado ?? "Sem fechamento."}</p>
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
          <Upload
            aberto={uploadAberto}
            aoFechar={() => setUploadAberto(false)}
            aoEnviar={async (arquivos) => {
              const novo = await api.enviarArquivos(arquivos); // erro sobe para o painel de upload
              await aplicar(novo);
              setUploadAberto(false);
              setAviso(`Mês fechado com os arquivos enviados: ${novo.tabelas.pendencias.length} pendências.`);
            }}
          />

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

function Status({ f }: { f: Fechamento }) {
  const v = f.validacoes;
  const itens: [boolean, string][] = [
    [v.rastro_ok, "Rastro fecha no centavo"],
    [v.integridade_ok, "Toda linha de entrada tem saída"],
  ];
  if (v.referencia) {
    itens.push([
      v.referencia.casos_referencia_ok === v.referencia.casos_referencia_total,
      `Referência manual ${v.referencia.casos_referencia_ok}/${v.referencia.casos_referencia_total}`,
    ]);
  }
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs" aria-label="Validações do fechamento">
      {itens.map(([ok, nome]) => (
        <li key={nome} className={`flex items-center gap-1 ${ok ? "text-tinta-2" : "font-medium text-erro"}`}>
          {ok ? <Check size={14} /> : <TriangleAlert size={14} />} {nome}
        </li>
      ))}
    </ul>
  );
}
