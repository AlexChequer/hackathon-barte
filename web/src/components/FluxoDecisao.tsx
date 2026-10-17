import { useEffect, useMemo, useState } from "react";
import { api, type Caso, type CasoDetalhe, type Decisao, type Tratamento } from "../api";
import { dinheiro } from "../format";

interface Props {
  caso: Caso;
  pendencia: { id_saida: string | null; tipo: string | null; motivo: string | null; valor_brl: string | null };
  aoAtualizar: () => void;
}

/**
 * Fluxo compacto: lista decisões/precedentes do caso, permite registrar proposta,
 * aprovar/rejeitar/revogar segundo o perfil, e registrar resultado operacional.
 * Preserva o visual existente (mesmas classes utilitárias do Tailwind).
 */
export function FluxoDecisao({ caso, pendencia, aoAtualizar }: Props) {
  const [detalhe, setDetalhe] = useState<CasoDetalhe | null>(null);
  const [precedentes, setPrecedentes] = useState<Decisao[]>([]);
  const [acoes, setAcoes] = useState<Tratamento[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [abrirForm, setAbrirForm] = useState(false);

  async function recarregar() {
    const [d, p, t] = await Promise.all([
      api.caso(caso.caso_hash),
      api.precedentes(caso.caso_hash).catch(() => ({ precedentes: [] })),
      api.tratamentos(),
    ]);
    setDetalhe(d);
    setPrecedentes(p.precedentes);
    setAcoes(t.acoes);
  }

  useEffect(() => {
    recarregar().catch((e) => setErro((e as Error).message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caso.caso_hash]);

  const acoesCompat = useMemo(() => {
    const tipo = pendencia.tipo ?? "";
    return acoes.filter(
      (a) => a.tipos_pendencia.includes(tipo) || (a.apenas_operacional && a.tipos_pendencia.length === 0)
    );
  }, [acoes, pendencia.tipo]);

  const pendente = detalhe?.decisoes.find((d) => d.status === "PENDENTE") ?? null;
  const aprovada = detalhe?.decisoes.find((d) => d.status === "APROVADA") ?? null;
  const resultado = detalhe?.resultados[0] ?? null;

  async function tratar<T>(acao: () => Promise<T>, msg: string) {
    try {
      await acao();
      setMensagem(msg);
      await recarregar();
      aoAtualizar();
    } catch (e) {
      setErro((e as Error).message);
    }
  }

  return (
    <div className="mt-4 rounded-md border border-linha bg-folha/50 p-3 text-sm">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-tinta-3">Ciclo de decisão</h3>
      {erro && <p className="mb-2 text-xs text-erro">{erro}</p>}
      {mensagem && <p className="mb-2 text-xs text-tinta-2">{mensagem}</p>}

      <HistoricoDecisoes decisoes={detalhe?.decisoes ?? []} />

      {aprovada && (
        <div className="mt-2 rounded border border-decisao/50 bg-decisao-fundo p-2 text-xs">
          <p>
            <strong>Tratamento aplicado:</strong> {aprovada.acao_tipo} ·
            aprovado por <strong>{aprovada.aprovador}</strong>
            {aprovada.aprovacao_externa?.aprovador && (
              <> (externamente: {aprovada.aprovacao_externa.aprovador})</>
            )}
          </p>
          <button
            onClick={() =>
              tratar(() => api.revogar(aprovada.id, "revogada pelo painel"), "Decisão revogada.")
            }
            className="mt-1 rounded border border-linha-forte px-2 py-0.5 text-xs hover:bg-papel"
          >
            Revogar
          </button>
        </div>
      )}

      {pendente && (
        <div className="mt-2 rounded border border-linha-forte bg-papel p-2 text-xs">
          <p>
            Proposta <strong>#{pendente.id}</strong> ({pendente.acao_tipo}) aguardando aprovação.
            Autor: {pendente.autor}.
          </p>
          <AprovarInline
            decisao={pendente}
            aoAprovar={(externa) =>
              tratar(
                () => api.aprovar(pendente.id, externa ? { aprovacao_externa: externa } : {}),
                "Decisão aprovada e aplicada."
              )
            }
            aoRejeitar={(motivo) => tratar(() => api.rejeitar(pendente.id, motivo), "Proposta rejeitada.")}
          />
        </div>
      )}

      {!pendente && !aprovada && (
        <button
          onClick={() => setAbrirForm((v) => !v)}
          className="mt-2 rounded border border-linha-forte px-2 py-1 text-xs hover:bg-papel"
        >
          {abrirForm ? "Fechar formulário" : "Registrar proposta de tratamento"}
        </button>
      )}

      {abrirForm && !pendente && !aprovada && (
        <PropostaForm
          caso={caso}
          pendencia={pendencia}
          acoesCompat={acoesCompat}
          aoProposto={() => {
            setAbrirForm(false);
            tratar(() => Promise.resolve(null), "Proposta registrada. Falta aprovação.");
          }}
        />
      )}

      <ResultadoOperacionalForm caso={caso} atual={resultado} aoAtualizar={() => tratar(() => Promise.resolve(null), "Resultado atualizado.")} />

      {precedentes.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs text-tinta-3 hover:text-tinta">
            Precedentes (não autorizam, só referência) · {precedentes.length}
          </summary>
          <ul className="mt-1 space-y-1 text-xs">
            {precedentes.map((p) => (
              <li key={p.id} className="rounded border border-linha-forte/60 bg-papel px-2 py-1">
                <span className="font-mono">{p.acao_tipo}</span> · {p.justificativa}
                <span className="ml-2 text-tinta-3">({p.status})</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function HistoricoDecisoes({ decisoes }: { decisoes: Decisao[] }) {
  if (!decisoes.length) return <p className="text-xs text-tinta-3">Nenhuma decisão registrada ainda.</p>;
  return (
    <ul className="space-y-1 text-xs">
      {decisoes.map((d) => (
        <li key={d.id} className="rounded border border-linha-forte/50 bg-papel px-2 py-1">
          <span className="font-mono">#{d.id}</span> · {d.acao_tipo} ·
          <span className={`ml-1 font-semibold ${corStatus(d.status)}`}>{d.status}</span>
          <div className="text-tinta-3">
            autor {d.autor} ({d.autor_perfil}) · versão {d.versao}
          </div>
          <div className="mt-0.5 text-tinta-2">{d.justificativa}</div>
        </li>
      ))}
    </ul>
  );
}

function corStatus(status: string): string {
  if (status === "APROVADA") return "text-decisao-tinta";
  if (status === "REJEITADA" || status === "REVOGADA" || status === "SUBSTITUIDA") return "text-tinta-3";
  return "text-decisao";
}

function AprovarInline({
  decisao,
  aoAprovar,
  aoRejeitar,
}: {
  decisao: Decisao;
  aoAprovar: (externa?: { aprovador?: string; evidencia?: string; data?: string }) => void;
  aoRejeitar: (motivo: string) => void;
}) {
  const [externa, setExterna] = useState({ aprovador: "", evidencia: "", data: "" });
  const [motivo, setMotivo] = useState("");

  return (
    <div className="mt-2 space-y-1">
      <details>
        <summary className="cursor-pointer text-xs text-tinta-3">Aprovação externa (opcional)</summary>
        <div className="mt-1 grid grid-cols-1 gap-1 sm:grid-cols-3">
          <input className="rounded border border-linha-forte px-1 py-0.5 text-xs"
            placeholder="Aprovador (ex.: Comercial por e-mail)"
            value={externa.aprovador} onChange={(e) => setExterna({ ...externa, aprovador: e.target.value })} />
          <input className="rounded border border-linha-forte px-1 py-0.5 text-xs"
            placeholder="Evidência (nº, link)"
            value={externa.evidencia} onChange={(e) => setExterna({ ...externa, evidencia: e.target.value })} />
          <input type="date" className="rounded border border-linha-forte px-1 py-0.5 text-xs"
            value={externa.data} onChange={(e) => setExterna({ ...externa, data: e.target.value })} />
        </div>
      </details>
      <div className="flex flex-wrap gap-1">
        <button
          onClick={() => aoAprovar(externa.aprovador ? externa : undefined)}
          className="rounded border border-decisao bg-decisao-fundo px-2 py-1 text-xs font-medium text-decisao-tinta hover:bg-decisao/20"
        >
          Confirmar aprovação
        </button>
        <input
          className="flex-1 rounded border border-linha-forte px-1 py-0.5 text-xs"
          placeholder="motivo da rejeição"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
        />
        <button
          disabled={!motivo}
          onClick={() => aoRejeitar(motivo)}
          className="rounded border border-linha-forte px-2 py-1 text-xs hover:bg-papel disabled:opacity-50"
        >
          Rejeitar
        </button>
      </div>
      <p className="text-[11px] text-tinta-3">
        A aprovação exige perfil compatível (R20): quem clica aqui vira o aprovador autenticado.
        {decisao.autor_perfil && (
          <> Autor atual: {decisao.autor}.</>
        )}
      </p>
    </div>
  );
}

function PropostaForm({
  caso,
  pendencia,
  acoesCompat,
  aoProposto,
}: {
  caso: Caso;
  pendencia: { id_saida: string | null; tipo: string | null };
  acoesCompat: Tratamento[];
  aoProposto: () => void;
}) {
  const [acaoTipo, setAcaoTipo] = useState(acoesCompat[0]?.tipo ?? "");
  const [justificativa, setJustificativa] = useState("");
  const [parametros, setParametros] = useState<Record<string, string>>({});
  const [escopo, setEscopo] = useState<"CASO" | "CONDICAO">("CASO");
  const [vigenciaInicio, setVigenciaInicio] = useState("");
  const [vigenciaFim, setVigenciaFim] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  const acao = acoesCompat.find((a) => a.tipo === acaoTipo);

  async function enviar() {
    setErro(null);
    try {
      await api.propor({
        caso_hash: caso.caso_hash,
        escopo,
        cnpj: caso.cnpj || undefined,
        acao_tipo: acaoTipo,
        parametros: montarParametros(acao, parametros),
        justificativa,
        vigencia_inicio: escopo === "CONDICAO" ? vigenciaInicio || undefined : undefined,
        vigencia_fim: escopo === "CONDICAO" ? vigenciaFim || undefined : undefined,
      });
      aoProposto();
    } catch (e) {
      setErro((e as Error).message);
    }
  }

  if (acoesCompat.length === 0) {
    return <p className="mt-2 text-xs text-tinta-3">Nenhuma ação suportada para o tipo {pendencia.tipo}.</p>;
  }

  return (
    <div className="mt-2 space-y-2 rounded border border-linha-forte bg-papel p-2 text-xs">
      <label className="block">
        <span className="text-tinta-3">Ação</span>
        <select
          className="mt-0.5 w-full rounded border border-linha-forte px-1 py-0.5"
          value={acaoTipo}
          onChange={(e) => setAcaoTipo(e.target.value)}
        >
          {acoesCompat.map((a) => (
            <option key={a.tipo} value={a.tipo}>
              {a.tipo} · aprova: {a.aprovado_por.join("/")}
            </option>
          ))}
        </select>
        {acao && <p className="mt-0.5 text-[11px] text-tinta-3">{acao.descricao}</p>}
      </label>

      <label className="block">
        <span className="text-tinta-3">Escopo</span>
        <select
          className="mt-0.5 w-full rounded border border-linha-forte px-1 py-0.5"
          value={escopo}
          onChange={(e) => setEscopo(e.target.value as "CASO" | "CONDICAO")}
        >
          <option value="CASO">Só este caso</option>
          <option value="CONDICAO">Condição reutilizável (CNPJ/vigência)</option>
        </select>
      </label>

      {escopo === "CONDICAO" && (
        <div className="grid grid-cols-2 gap-1">
          <input type="date" placeholder="início" value={vigenciaInicio}
            onChange={(e) => setVigenciaInicio(e.target.value)}
            className="rounded border border-linha-forte px-1 py-0.5" />
          <input type="date" placeholder="fim" value={vigenciaFim}
            onChange={(e) => setVigenciaFim(e.target.value)}
            className="rounded border border-linha-forte px-1 py-0.5" />
        </div>
      )}

      {(acao?.parametros_obrigatorios ?? []).map((p) => (
        <label className="block" key={p}>
          <span className="text-tinta-3">{p}</span>
          <input
            className="mt-0.5 w-full rounded border border-linha-forte px-1 py-0.5"
            value={parametros[p] ?? ""}
            onChange={(e) => setParametros((prev) => ({ ...prev, [p]: e.target.value }))}
          />
        </label>
      ))}

      <label className="block">
        <span className="text-tinta-3">Justificativa</span>
        <textarea
          className="mt-0.5 w-full rounded border border-linha-forte px-1 py-0.5"
          rows={2}
          value={justificativa}
          onChange={(e) => setJustificativa(e.target.value)}
        />
      </label>

      {erro && <p className="text-xs text-erro">{erro}</p>}
      <button
        disabled={!justificativa.trim()}
        onClick={enviar}
        className="rounded border border-linha-forte px-2 py-1 text-xs hover:bg-folha disabled:opacity-50"
      >
        Salvar proposta
      </button>
    </div>
  );
}

function montarParametros(acao: Tratamento | undefined, raw: Record<string, string>): Record<string, unknown> {
  if (!acao) return raw;
  const out: Record<string, unknown> = {};
  for (const p of acao.parametros_obrigatorios) {
    if (p === "taxas") {
      try {
        out[p] = JSON.parse(raw[p] || "{}");
      } catch {
        out[p] = raw[p];
      }
    } else {
      out[p] = raw[p];
    }
  }
  return out;
}

function ResultadoOperacionalForm({
  caso,
  atual,
  aoAtualizar,
}: {
  caso: Caso;
  atual: { status: string; saldo_centavos: number | null; evidencia: string | null } | null;
  aoAtualizar: () => void;
}) {
  const [status, setStatus] = useState<"ABERTO" | "AGUARDANDO_RETORNO" | "PARCIAL" | "RESOLVIDO">("AGUARDANDO_RETORNO");
  const [saldoCentavos, setSaldoCentavos] = useState("");
  const [evidencia, setEvidencia] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  async function enviar() {
    setErro(null);
    try {
      await api.registrarResultado(caso.caso_hash, {
        status,
        saldo_centavos: saldoCentavos ? Number(saldoCentavos) : undefined,
        evidencia: evidencia || undefined,
      });
      aoAtualizar();
      setSaldoCentavos("");
      setEvidencia("");
    } catch (e) {
      setErro((e as Error).message);
    }
  }

  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-xs text-tinta-3">Resultado operacional (independente do fechamento)</summary>
      {atual && (
        <p className="mt-1 text-[11px] text-tinta-3">
          Atual: {atual.status}{" "}
          {atual.saldo_centavos != null && <>· saldo {dinheiro(atual.saldo_centavos / 100)}</>}
          {atual.evidencia && <>· evidência: {atual.evidencia}</>}
        </p>
      )}
      <div className="mt-1 grid grid-cols-1 gap-1 sm:grid-cols-3">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as typeof status)}
          className="rounded border border-linha-forte px-1 py-0.5 text-xs"
        >
          <option>ABERTO</option>
          <option>AGUARDANDO_RETORNO</option>
          <option>PARCIAL</option>
          <option>RESOLVIDO</option>
        </select>
        <input
          placeholder="saldo em centavos (parcial)"
          value={saldoCentavos}
          onChange={(e) => setSaldoCentavos(e.target.value)}
          className="rounded border border-linha-forte px-1 py-0.5 text-xs"
        />
        <input
          placeholder="evidência (obrigatória se RESOLVIDO)"
          value={evidencia}
          onChange={(e) => setEvidencia(e.target.value)}
          className="rounded border border-linha-forte px-1 py-0.5 text-xs"
        />
      </div>
      {erro && <p className="mt-1 text-xs text-erro">{erro}</p>}
      <button
        onClick={enviar}
        className="mt-1 rounded border border-linha-forte px-2 py-1 text-xs hover:bg-folha"
      >
        Registrar resultado
      </button>
    </details>
  );
}
