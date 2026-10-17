import { useEffect, useMemo, useState } from "react";
import { api, type Fechamento, type Linha } from "../api";
import { cnpj, data, dinheiro, pct } from "../format";
import { nomesPorCnpj } from "./Pendencias";
import { Valor } from "./Valor";

const ARQUIVO: Record<string, string> = {
  orbe: "Relatório Orbe (01)",
  orbe_ajustes: "Ajustes tardios Orbe (06)",
  ponte: "Relatório Ponte (03)",
  aurora: "Extrato Aurora (05a)",
  meridiano: "Extrato Meridiano (05b)",
  taxas: "Planilha de taxas (02)",
};

const th = "py-2.5 pr-4 text-left text-xs font-medium text-tinta-3";
const td = "py-2 pr-4";

function Filtros<T extends string>({ opcoes, atual, aoMudar }: { opcoes: [T, string, number][]; atual: T; aoMudar: (v: T) => void }) {
  return (
    <div role="tablist" className="mb-4 flex flex-wrap gap-1.5">
      {opcoes.map(([v, nome, n]) => (
        <button
          key={v}
          role="tab"
          aria-selected={atual === v}
          onClick={() => aoMudar(v)}
          className={`rounded-full border px-3 py-1 text-sm transition-colors ${
            atual === v ? "border-tinta bg-tinta text-folha" : "border-linha-forte text-tinta-2 hover:bg-folha"
          }`}
        >
          {nome} <span className={atual === v ? "text-folha/70" : "text-tinta-3"}>{n}</span>
        </button>
      ))}
    </div>
  );
}

/** Faixa de razão: os totais do mês em uma linha, como no rodapé de um livro contábil. */
export function Razao({ f }: { f: Fechamento }) {
  const t = f.totais;
  const itens: [string, string, string][] = [
    ["Comissão checkout", t.comissao_checkout, "a faturar dos lojistas"],
    ["Comissão remessa", t.comissao_remessa, "nota única para a Ponte"],
    ["Notas a emitir", t.notas, `${f.tabelas.notas.length} notas`],
    ["Cobrar da Orbe", t.cobrar_orbe, "taxa diferente do contrato"],
    ["Devolver ao lojista", t.devolver_condicao, "condição comercial não avisada"],
    ["Contestar com a Ponte", t.divergencia_remessa, "spread acima do contrato"],
  ];
  return (
    <dl className="grid grid-cols-2 border-y border-linha-forte md:grid-cols-3 xl:grid-cols-6">
      {itens.map(([nome, valor, nota]) => (
        <div key={nome} className="border-linha py-4 pr-4 [&:not(:last-child)]:border-r md:pl-4 md:first:pl-0">
          <dt className="text-xs text-tinta-3">{nome}</dt>
          <dd className="num mt-1 text-lg font-semibold">{dinheiro(valor)}</dd>
          <dd className="text-xs text-tinta-3">{nota}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Numeros({ f }: { f: Fechamento }) {
  const [linha, setLinha] = useState<"CHECKOUT" | "REMESSA">("CHECKOUT");
  const com = f.tabelas.comissoes
    .filter((c) => c.linha_negocio === linha)
    .sort((a, b) => Number(b.comissao_brl) - Number(a.comissao_brl));
  const notas = f.tabelas.notas;
  return (
    <div className="space-y-10">
      <Razao f={f} />
      <div className="grid gap-10 xl:grid-cols-[3fr_2fr]">
        <section>
          <h2 className="mb-3 text-[15px] font-semibold">Comissão por lojista</h2>
          <Filtros
            opcoes={[
              ["CHECKOUT", "Checkout", f.tabelas.comissoes.filter((c) => c.linha_negocio === "CHECKOUT").length],
              ["REMESSA", "Remessa", f.tabelas.comissoes.filter((c) => c.linha_negocio === "REMESSA").length],
            ]}
            atual={linha}
            aoMudar={setLinha}
          />
          <table className="w-full text-sm">
            <thead className="border-b border-linha-forte">
              <tr>
                <th className={th}>Lojista</th>
                <th className={th}>CNPJ</th>
                <th className={`${th} text-right`}>Comissão</th>
              </tr>
            </thead>
            <tbody>
              {com.map((c) => (
                <tr key={c.id_saida} className="border-b border-linha">
                  <td className={td}>{c.lojista}</td>
                  <td className={`${td} num text-tinta-2`}>{cnpj(c.cnpj)}</td>
                  <td className={`${td} pr-0 text-right`}>
                    <Valor id={c.id_saida!} valor={c.comissao_brl} titulo={`Comissão ${linha.toLowerCase()} · ${c.lojista}`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section>
          <h2 className="mb-3 text-[15px] font-semibold">Notas a emitir</h2>
          <p className="mb-4 text-sm text-tinta-2">Uma por lojista no checkout; uma única para a Ponte na remessa. Saldo zero ou negativo não emite.</p>
          <table className="w-full text-sm">
            <thead className="border-b border-linha-forte">
              <tr>
                <th className={th}>Tomador</th>
                <th className={`${th} text-right`}>Valor</th>
              </tr>
            </thead>
            <tbody>
              {notas.map((n) => (
                <tr key={n.id_saida} className="border-b border-linha" title={n.discriminacao ?? ""}>
                  <td className={td}>
                    {n.tomador}
                    {n.linha_negocio === "REMESSA" && <span className="ml-2 text-xs text-tinta-3">remessa</span>}
                  </td>
                  <td className={`${td} pr-0 text-right`}>
                    <Valor id={n.id_saida!} valor={n.valor_brl} titulo={`Nota · ${n.tomador}`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}

type TipoDiv = "CK-DIV" | "CK-COND" | "RM-DIV";
const NOME_DIV: Record<TipoDiv, string> = {
  "CK-DIV": "Orbe cobrou diferente do contrato",
  "CK-COND": "Condição comercial não avisada",
  "RM-DIV": "Ponte cobrou spread acima",
};

export function Divergencias({ f }: { f: Fechamento }) {
  const todas = f.tabelas.divergencias;
  const [tipo, setTipo] = useState<TipoDiv>("CK-DIV");
  const lojistas = useMemo(() => nomesPorCnpj(f), [f]);
  const grupos = useMemo(() => {
    const por: Record<string, Linha[]> = {};
    for (const d of todas.filter((d) => d.id_saida?.startsWith(`${tipo}-`))) (por[d.cnpj ?? "—"] ??= []).push(d);
    return Object.entries(por);
  }, [todas, tipo]);
  const [aberto, setAberto] = useState<string | null>(null);
  const contar = (t: TipoDiv) => todas.filter((d) => d.id_saida?.startsWith(`${t}-`)).length;

  return (
    <div>
      <p className="mb-5 max-w-[70ch] text-tinta-2">
        Uma linha por transação ou operação em que a taxa cobrada difere da contratada. O valor é bruto × (cobrada −
        contratada), arredondado por linha. Centavo de truncamento da Orbe não entra.
      </p>
      <Filtros opcoes={(Object.keys(NOME_DIV) as TipoDiv[]).map((t) => [t, NOME_DIV[t], contar(t)])} atual={tipo} aoMudar={setTipo} />
      <table className="w-full text-sm">
        <thead className="border-b border-linha-forte">
          <tr>
            <th className={th}>Lojista</th>
            <th className={th}>Linhas</th>
            <th className={th}>Contrato × cobrado</th>
            <th className={`${th} text-right`}>Diferença</th>
          </tr>
        </thead>
        <tbody>
          {grupos.map(([doc, linhas]) => {
            const total = linhas.reduce((t, l) => t + Number(l.diferenca_brl), 0);
            const pares = [...new Set(linhas.map((l) => `${pct(l.taxa_contratada_pct)} × ${pct(l.taxa_aplicada_pct)}`))];
            return [
              <tr key={doc} className="cursor-pointer border-b border-linha hover:bg-folha" onClick={() => setAberto(aberto === doc ? null : doc)}>
                <td className={td}>{lojistas[doc] ?? cnpj(doc)}</td>
                <td className={`${td} num text-tinta-2`}>{linhas.length}</td>
                <td className={`${td} num text-tinta-2`}>{pares.slice(0, 2).join(", ")}{pares.length > 2 ? " …" : ""}</td>
                <td className={`${td} num pr-0 text-right font-medium`}>{dinheiro(total)}</td>
              </tr>,
              aberto === doc &&
                linhas.map((l) => (
                  <tr key={l.id_saida} className="border-b border-linha/60 bg-folha text-[13px]">
                    <td className={`${td} pl-6 font-mono text-tinta-2`}>{l.ref_origem}</td>
                    <td className={td} />
                    <td className={`${td} num text-tinta-2`}>{pct(l.taxa_contratada_pct)} × {pct(l.taxa_aplicada_pct)}</td>
                    <td className={`${td} pr-0 text-right`}>
                      <Valor id={l.id_saida!} valor={l.diferenca_brl} titulo={`Divergência · ${l.ref_origem}`} />
                    </td>
                  </tr>
                )),
            ];
          })}
        </tbody>
      </table>
    </div>
  );
}

type FiltroArquivo = "TODOS" | keyof typeof ARQUIVO;
const LIMITE_RASTRO = 500;

export function Rastro({ f }: { f: Fechamento }) {
  const [arquivo, setArquivo] = useState<FiltroArquivo>("TODOS");
  const [busca, setBusca] = useState("");
  const [todas, setTodas] = useState<Linha[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    setTodas(null);
    setErro(null);
    api.rastroCompleto().then((r) => setTodas(r.linhas)).catch((e: Error) => setErro(e.message));
  }, [f.execucao_id]);

  const filtradas = useMemo(() => {
    if (!todas) return [];
    const q = busca.trim().toLowerCase();
    return todas.filter((l) => {
      if (arquivo !== "TODOS" && l.arquivo_origem !== arquivo) return false;
      if (!q) return true;
      return `${l.id_saida} ${l.ref_origem} ${l.metadata ?? ""}`.toLowerCase().includes(q);
    });
  }, [todas, arquivo, busca]);

  const porArquivo = useMemo(() => {
    const c: Record<string, number> = {};
    (todas ?? []).forEach((l) => {
      const k = l.arquivo_origem ?? "—";
      c[k] = (c[k] ?? 0) + 1;
    });
    return c;
  }, [todas]);

  const visiveis = filtradas.slice(0, LIMITE_RASTRO);
  const opcoes: [FiltroArquivo, string, number][] = [
    ["TODOS", "Todos", todas?.length ?? 0],
    ...(Object.keys(ARQUIVO) as (keyof typeof ARQUIVO)[])
      .filter((k) => porArquivo[k])
      .map((k) => [k, ARQUIVO[k], porArquivo[k]] as [FiltroArquivo, string, number]),
  ];

  return (
    <div>
      <p className="mb-5 max-w-[70ch] text-tinta-2">
        Uma linha para cada centavo que entra em um número de saída. Toda saída precisa ter rastro cuja soma bate exata com o
        valor dela. Clique no valor para ver só o rastro de um id.
      </p>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Filtros opcoes={opcoes} atual={arquivo} aoMudar={setArquivo} />
        <input
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar id de saída, origem ou metadado"
          className="mb-4 w-72 rounded-md border border-linha-forte bg-folha px-3 py-1.5 text-sm placeholder:text-tinta-3"
        />
      </div>
      {erro && <p className="text-sm text-erro">{erro}</p>}
      {!todas && !erro && <p className="text-sm text-tinta-3">Carregando o rastro…</p>}
      {todas && (
        <>
          <p className="mb-2 text-xs text-tinta-3">
            {filtradas.length.toLocaleString("pt-BR")} de {todas.length.toLocaleString("pt-BR")} linhas
            {filtradas.length > LIMITE_RASTRO && ` · mostrando as primeiras ${LIMITE_RASTRO}`}
          </p>
          <table className="w-full text-sm">
            <thead className="border-b border-linha-forte">
              <tr>
                <th className={th}>Id de saída</th>
                <th className={th}>Arquivo</th>
                <th className={th}>Linha de origem</th>
                <th className={th}>Metadado</th>
                <th className={`${th} text-right`}>Valor</th>
              </tr>
            </thead>
            <tbody>
              {visiveis.map((l, i) => (
                <tr key={`${l.id_saida}-${l.ref_origem}-${i}`} className="border-b border-linha">
                  <td className={`${td} font-mono text-[13px]`}>{l.id_saida}</td>
                  <td className={`${td} text-tinta-2`}>{ARQUIVO[l.arquivo_origem ?? ""] ?? l.arquivo_origem}</td>
                  <td className={`${td} font-mono text-[13px]`}>{l.ref_origem}</td>
                  <td className={`${td} font-mono text-[12px] text-tinta-3`}>{l.metadata ?? ""}</td>
                  <td className={`${td} pr-0 text-right`}>
                    <Valor id={l.id_saida!} valor={l.valor} titulo={l.id_saida ?? ""} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

export function Lancamentos({ f }: { f: Fechamento }) {
  const [banco, setBanco] = useState<"AURORA" | "MERIDIANO">("AURORA");
  const [busca, setBusca] = useState("");
  const todos = f.tabelas.lancamentos;
  const linhas = todos.filter(
    (l) => l.banco === banco && (!busca || `${l.descricao} ${l.conta_codigo}`.toLowerCase().includes(busca.toLowerCase())),
  );
  return (
    <div>
      <p className="mb-5 max-w-[70ch] text-tinta-2">
        Cada movimento dos extratos com a conta de contrapartida no plano (R9). Classificação por regra; o que nenhuma
        regra cobre fica sem conta e vira pendência.
      </p>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Filtros
          opcoes={[
            ["AURORA", "Aurora", todos.filter((l) => l.banco === "AURORA").length],
            ["MERIDIANO", "Meridiano", todos.filter((l) => l.banco === "MERIDIANO").length],
          ]}
          atual={banco}
          aoMudar={setBanco}
        />
        <input
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar descrição ou conta"
          className="mb-4 w-64 rounded-md border border-linha-forte bg-folha px-3 py-1.5 text-sm placeholder:text-tinta-3"
        />
      </div>
      <table className="w-full text-sm">
        <thead className="border-b border-linha-forte">
          <tr>
            <th className={th}>Data</th>
            <th className={th}>Origem</th>
            <th className={th}>Descrição</th>
            <th className={th}>Conta</th>
            <th className={`${th} text-right`}>Valor</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={l.id_saida} className="border-b border-linha" title={l.motivo ?? ""}>
              <td className={`${td} num whitespace-nowrap text-tinta-2`}>{data(l.data)}</td>
              <td className={`${td} font-mono text-[13px] text-tinta-3`}>{l.ref_origem}</td>
              <td className={td}>{l.descricao}</td>
              <td className={`${td} num ${l.conta_codigo ? "" : "font-medium text-decisao-tinta"}`}>{l.conta_codigo ?? "sem regra"}</td>
              <td className={`${td} pr-0 text-right`}>
                <Valor id={l.id_saida!} valor={l.valor} titulo={l.descricao ?? ""} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
