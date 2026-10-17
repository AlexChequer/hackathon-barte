import { AnimatePresence, motion } from "motion/react";
import { Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Condicao, type Fechamento, type SinalAberto } from "../api";
import { cnpj, data, MODALIDADES } from "../format";
import { Valor } from "./Valor";

function resumoTaxas(c: Condicao): string {
  const valores = Object.values(c.taxas).map(Number);
  if (Object.keys(c.taxas).length === Object.keys(MODALIDADES).length && valores.every((v) => v === 0))
    return "Isenção total: 0% em todas as modalidades e na antecipação";
  return Object.entries(c.taxas)
    .map(([k, v]) => `${MODALIDADES[k] ?? k} ${(Number(v) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 4 })}%`)
    .join(" · ");
}

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/** Vigência no ano: onde a condição começa, onde termina e onde está o mês em fechamento. */
function Vigencia({ c, competencia }: { c: Condicao; competencia: string }) {
  const ano = Number(c.inicio.slice(0, 4));
  const pos = (iso: string) => {
    const [a, m, d] = iso.split("-").map(Number);
    if (a < ano) return 0;
    if (a > ano) return 100;
    return ((m - 1 + (d - 1) / 31) / 12) * 100;
  };
  const ini = pos(c.inicio);
  const fim = c.fim ? pos(c.fim) + 100 / 12 / 31 : 100;
  const atual = Number(competencia.slice(0, 4)) === ano ? ((Number(competencia.slice(5, 7)) - 0.5) / 12) * 100 : null;
  return (
    <div className="mt-3">
      <div className="relative h-2 rounded-full bg-linha">
        <motion.div
          className="absolute inset-y-0 rounded-full bg-decisao"
          style={{ left: `${ini}%` }}
          initial={{ width: 0 }}
          animate={{ width: `${fim - ini}%` }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        />
        {atual != null && (
          <div className="absolute -top-1 h-4 w-px bg-tinta" style={{ left: `${atual}%` }} title="Mês em fechamento" />
        )}
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] text-tinta-3">
        {MESES.map((m) => (
          <span key={m}>{m}</span>
        ))}
      </div>
    </div>
  );
}

/** O que a condição causou neste mês: devolução que sai do bolso da Tarvo, com rastro. */
function Impacto({ c, f }: { c: Condicao; f: Fechamento }) {
  const p = f.tabelas.pendencias.find((x) => x.tipo === "CONDICAO_NAO_INFORMADA_ORBE" && x.ref_origem === c.cnpj);
  const linhas = f.tabelas.divergencias.filter((d) => d.id_saida?.startsWith("CK-COND-") && d.cnpj === c.cnpj).length;
  if (!p) return <p className="mt-3 text-sm text-tinta-2">Neste mês a Orbe já cobrou a taxa da condição: nada a devolver.</p>;
  return (
    <p className="mt-3 flex flex-wrap items-baseline gap-x-1.5 rounded-md bg-decisao-fundo px-3 py-2 text-sm text-decisao-tinta">
      Neste mês: a Orbe cobrou a taxa da planilha em {linhas} transações. Devolver ao lojista
      <Valor id={p.id_saida!} valor={p.valor_brl} titulo={`Devolução · ${c.lojista ?? cnpj(c.cnpj)}`} forte />
      <span className="text-decisao-tinta/80">(não cobrar da Orbe; avisar a Orbe e atualizar a planilha).</span>
    </p>
  );
}

export function Condicoes({
  fechamento,
  competencia,
  sinalInicial,
  aoGravar,
}: {
  fechamento: Fechamento;
  competencia: string;
  sinalInicial: SinalAberto | null;
  aoGravar: (msg: string) => Promise<void>;
}) {
  const [conds, setConds] = useState<Condicao[]>([]);
  const [formAberto, setFormAberto] = useState(Boolean(sinalInicial));

  const carregar = () => api.condicoes().then((r) => setConds(r.condicoes));
  useEffect(() => {
    carregar();
  }, []);
  useEffect(() => setFormAberto(Boolean(sinalInicial) || formAberto), [sinalInicial]); // eslint-disable-line

  return (
    <div className="grid gap-10 xl:grid-cols-[1fr_28rem]">
      <section>
        <p className="mb-6 max-w-[68ch] text-tinta-2">
          Acordos do comercial que mudam a taxa sem estar na planilha. O fechamento aplica a condição vigente na data da
          venda e separa o que a Orbe cobrou por não saber dela. Fica registrado quem aprovou e quando (R20).
        </p>
        <ul className="space-y-4">
          {conds.map((c) => (
            <li key={c.id} className="rounded-lg border border-linha bg-folha p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="font-semibold">{c.lojista || cnpj(c.cnpj)}</h3>
                <span className="font-mono text-xs text-tinta-3">{c.id}</span>
              </div>
              <p className="mt-1 text-sm text-tinta-2">{resumoTaxas(c)}</p>
              <p className="mt-1 text-sm">
                de <strong className="num font-medium">{data(c.inicio)}</strong> até{" "}
                <strong className="num font-medium">{c.fim ? data(c.fim) : "sem fim"}</strong>
              </p>
              <Vigencia c={c} competencia={competencia} />
              {c.descricao && <p className="mt-3 max-w-[68ch] text-sm text-tinta-2">{c.descricao}</p>}
              <Impacto c={c} f={fechamento} />
              <p className="mt-2 text-xs text-tinta-3">
                Aprovado por {c.aprovado_por} · fonte {c.fonte} · registrado por {c.registrado_por ?? "—"} em {data(c.registrado_em)}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        {!formAberto ? (
          <button
            onClick={() => setFormAberto(true)}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-linha-forte py-4 text-sm font-medium text-tinta-2 transition-colors hover:border-decisao hover:text-decisao-tinta"
          >
            <Plus size={16} /> Registrar condição comercial
          </button>
        ) : (
          <FormCondicao
            sinal={sinalInicial}
            aoCancelar={() => setFormAberto(false)}
            aoGravar={async (msg) => {
              await carregar();
              setFormAberto(false);
              await aoGravar(msg);
            }}
          />
        )}
      </section>
    </div>
  );
}

function FormCondicao({
  sinal,
  aoCancelar,
  aoGravar,
}: {
  sinal: SinalAberto | null;
  aoCancelar: () => void;
  aoGravar: (msg: string) => Promise<void>;
}) {
  const [lojistas, setLojistas] = useState<{ cnpj: string; lojista: string }[]>([]);
  const [doc, setDoc] = useState(sinal?.cnpj ?? "");
  const [taxas, setTaxas] = useState<Record<string, string>>({});
  const [inicio, setInicio] = useState("");
  const [fim, setFim] = useState("");
  const [descricao, setDescricao] = useState(sinal ? `Planilha L${sinal.linha}: "${sinal.texto}"` : "");
  const [fonte, setFonte] = useState(sinal ? `pendência ${sinal.id_saida}` : "");
  const [aprovado, setAprovado] = useState("Comercial");
  const [registrador, setRegistrador] = useState("Helena");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api.lojistas().then(setLojistas);
  }, []);

  const campo = "w-full rounded-md border border-linha-forte bg-folha px-3 py-2 text-sm";
  const rotulo = "mb-1 block text-xs font-medium text-tinta-2";

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setErro(null);
    const marcadas = Object.entries(taxas).filter(([, v]) => v.trim() !== "");
    if (!doc) return setErro("Escolha o lojista.");
    if (marcadas.length === 0) return setErro("Informe ao menos uma taxa (0 para isenção).");
    if (!inicio) return setErro("Informe a data de início.");
    setEnviando(true);
    try {
      const r = await api.registrarCondicao({
        cnpj: doc,
        lojista: lojistas.find((l) => l.cnpj === doc)?.lojista,
        taxas: Object.fromEntries(marcadas.map(([k, v]) => [k, String(Number(v.replace(",", ".")) / 100)])),
        inicio,
        fim: fim || null,
        descricao,
        fonte: fonte || "registrado na tela",
        aprovado_por: aprovado,
        registrado_por: registrador,
      });
      await aoGravar(`${r.condicao.id} gravada. Fechamento refeito: ${r.fechamento.tabelas.pendencias.length} pendências.`);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <motion.form
      onSubmit={enviar}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-4 rounded-lg border border-linha bg-folha p-5"
    >
      <h3 className="font-semibold">Registrar condição comercial</h3>
      {sinal && (
        <p className="rounded-md bg-decisao-fundo px-3 py-2 text-sm text-decisao-tinta">
          Da pendência: {sinal.lojista}, planilha L{sinal.linha} ({sinal.campo}): “{sinal.texto}”
        </p>
      )}
      <div>
        <label className={rotulo} htmlFor="lojista">Lojista</label>
        <select id="lojista" value={doc} onChange={(e) => setDoc(e.target.value)} className={campo}>
          <option value="">Escolha…</option>
          {lojistas.map((l) => (
            <option key={l.cnpj} value={l.cnpj}>{l.lojista} · {cnpj(l.cnpj)}</option>
          ))}
        </select>
      </div>
      <fieldset>
        <legend className={rotulo}>Taxa contratada por modalidade, em % (deixe vazio o que não muda)</legend>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(MODALIDADES).map(([k, nome]) => (
            <label key={k} className="flex items-center justify-between gap-2 rounded-md border border-linha px-3 py-1.5 text-sm">
              <span className="whitespace-nowrap text-tinta-2">{nome}</span>
              <input
                inputMode="decimal"
                value={taxas[k] ?? ""}
                onChange={(e) => setTaxas({ ...taxas, [k]: e.target.value })}
                placeholder="—"
                className="num w-14 min-w-0 bg-transparent text-right outline-none"
                aria-label={`${nome} em %`}
              />
            </label>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setTaxas(Object.fromEntries(Object.keys(MODALIDADES).map((k) => [k, "0"])))}
          className="mt-2 text-xs font-medium text-decisao-tinta underline"
        >
          Isenção total (0% em tudo)
        </button>
      </fieldset>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={rotulo} htmlFor="inicio">Vale a partir de</label>
          <input id="inicio" type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} className={campo} />
        </div>
        <div>
          <label className={rotulo} htmlFor="fim">Até</label>
          <input id="fim" type="date" value={fim} onChange={(e) => setFim(e.target.value)} className={campo} />
        </div>
      </div>
      <div>
        <label className={rotulo} htmlFor="descricao">O que foi combinado</label>
        <textarea id="descricao" rows={2} value={descricao} onChange={(e) => setDescricao(e.target.value)} className={campo} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={rotulo} htmlFor="aprovado">Aprovado por</label>
          <select id="aprovado" value={aprovado} onChange={(e) => setAprovado(e.target.value)} className={campo}>
            <option>Comercial</option>
            <option>Financeiro</option>
          </select>
        </div>
        <div>
          <label className={rotulo} htmlFor="registrador">Registrado por</label>
          <input id="registrador" value={registrador} onChange={(e) => setRegistrador(e.target.value)} className={campo} />
        </div>
      </div>
      <div>
        <label className={rotulo} htmlFor="fonte">Fonte (e-mail, aditivo, pendência)</label>
        <input id="fonte" value={fonte} onChange={(e) => setFonte(e.target.value)} className={campo} />
      </div>
      <AnimatePresence>
        {erro && (
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} role="alert" className="text-sm text-erro">
            {erro}
          </motion.p>
        )}
      </AnimatePresence>
      <div className="flex gap-2 pt-1">
        <button
          type="submit"
          disabled={enviando}
          className="rounded-md bg-tinta px-4 py-2 text-sm font-medium text-folha transition-opacity disabled:opacity-50"
        >
          {enviando ? "Gravando e refazendo o fechamento…" : "Gravar e refazer o fechamento"}
        </button>
        <button type="button" onClick={aoCancelar} className="rounded-md px-3 py-2 text-sm text-tinta-2 hover:bg-papel">
          Cancelar
        </button>
      </div>
    </motion.form>
  );
}
