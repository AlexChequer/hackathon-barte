export type Linha = Record<string, string | null>;

export interface Fechamento {
  competencia: string;
  execucao_id: number;
  pasta_saida: string;
  regras_versao: string;
  duracao_s: number;
  arquivos: { nome: string; bytes: number; opcional: boolean }[];
  bloqueios: Bloqueio[];
  validacoes: {
    rastro_ok: boolean;
    integridade_ok: boolean;
    problemas: string[];
    referencia: { casos_referencia_ok: number; casos_referencia_total: number } | null;
  };
  totais: Record<
    "comissao_checkout" | "comissao_remessa" | "cobrar_orbe" | "devolver_condicao" | "divergencia_remessa" | "notas",
    string
  >;
  tabelas: Record<"comissoes" | "divergencias" | "notas" | "lancamentos" | "pendencias", Linha[]>;
  casos: Record<string, Caso>;
  aplicacoes_decisoes: { caso_hash: string; decisao_id: number; escopo: string; acao_tipo: string }[];
  rascunhos?: Rascunho[];
}

/** Rascunho de mensagem para um destinatário do fechamento (P36). */
export interface Rascunho {
  chave: string;
  destinatario: string;
  papel: "contraparte" | "lojista" | "interno";
  pendencias: string[];
  status: "gerado" | "indisponivel" | "reprovado" | "erro";
  assunto: string;
  corpo: string;
  anexo: string[];
  aviso: string;
}

export interface Caso {
  caso_hash: string;
  tipo: string;
  cnpj: string;
  ref: string;
  competencia: string;
  composicao: string[];
}

export interface Tratamento {
  tipo: string;
  descricao: string;
  aprovado_por: string[];
  altera_referencia: boolean;
  altera_calculo: boolean;
  apenas_operacional: boolean;
  parametros_obrigatorios: string[];
  tipos_pendencia: string[];
}

export interface Decisao {
  id: number;
  caso_hash: string | null;
  escopo: "CASO" | "CONDICAO";
  acao_tipo: string;
  status: "PENDENTE" | "APROVADA" | "REJEITADA" | "REVOGADA" | "SUBSTITUIDA";
  versao: number;
  justificativa: string;
  evidencias?: unknown[];
  parametros?: Record<string, unknown>;
  autor: string;
  autor_perfil: string;
  aprovador: string | null;
  aprovador_perfil: string | null;
  aprovado_em: string | null;
  aprovacao_externa?: { aprovador?: string; evidencia?: string; data?: string };
  criado_em: string;
  substitui_id: number | null;
}

export interface ResultadoOperacional {
  id: number;
  caso_hash: string;
  status: "ABERTO" | "AGUARDANDO_RETORNO" | "PARCIAL" | "RESOLVIDO";
  saldo_centavos: number | null;
  operacoes?: string[];
  evidencia: string | null;
  descricao: string | null;
  autor: string;
  timestamp: string;
}

export interface CasoDetalhe {
  decisoes: Decisao[];
  eventos: { tipo_evento: string; timestamp: string; autor: string | null; payload?: Record<string, unknown> }[];
  resultados: ResultadoOperacional[];
}

export interface Bloqueio {
  frente: string;
  faltando: string[];
  parcial: boolean;
  nao_sai: string;
  motivo_layout?: string;
}

export interface Condicao {
  id: string;
  cnpj: string;
  lojista?: string;
  taxas: Record<string, string>;
  inicio: string;
  fim: string | null;
  descricao?: string;
  fonte: string;
  aprovado_por: string;
  registrado_por?: string;
  registrado_em?: string;
}

export interface SinalAberto {
  id_saida: string;
  cnpj: string;
  lojista: string;
  linha: number;
  campo: string;
  texto: string;
  metodo: string;
}

/** Identidade do operador: usada só no header, nunca como aprovador autenticado. */
export interface Operador {
  nome: string;
  perfil: "financeiro" | "comercial" | "operador";
}

let operadorAtual: Operador = (() => {
  const salvo = typeof localStorage !== "undefined" ? localStorage.getItem("tarvo:operador") : null;
  if (salvo) try { return JSON.parse(salvo) as Operador; } catch { /* ignora */ }
  return { nome: "Fox AI", perfil: "operador" };
})();

export function definirOperador(op: Operador) {
  operadorAtual = op;
  if (typeof localStorage !== "undefined") localStorage.setItem("tarvo:operador", JSON.stringify(op));
}

export function operador(): Operador {
  return operadorAtual;
}

function headersOperador(): HeadersInit {
  return { "X-Tarvo-Usuario": operadorAtual.nome, "X-Tarvo-Perfil": operadorAtual.perfil };
}

async function pedir<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}));
    throw new Error(typeof corpo.detail === "string" ? corpo.detail : `Erro ${r.status} em ${url}`);
  }
  return r.json() as Promise<T>;
}

const json = (corpo: unknown, autenticado = false): RequestInit => ({
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    ...(autenticado ? headersOperador() : {}),
  },
  body: JSON.stringify(corpo),
});

export const api = {
  fechamento: () => pedir<Fechamento>("/api/fechamento"),
  fechar: () => pedir<Fechamento>("/api/fechar", { method: "POST" }),
  rastro: (id: string) => pedir<{ id_saida: string; linhas: Linha[] }>(`/api/rastro/${encodeURIComponent(id)}`),
  rastroCompleto: () => pedir<{ linhas: Linha[] }>("/api/rastro"),
  lojistas: () => pedir<{ cnpj: string; lojista: string }[]>("/api/lojistas"),
  condicoes: () => pedir<{ condicoes: Condicao[]; sinais_resolvidos: Linha[] }>("/api/condicoes"),
  sinais: () => pedir<SinalAberto[]>("/api/sinais"),
  registrarCondicao: (c: Omit<Condicao, "id">) =>
    pedir<{ condicao: Condicao; fechamento: Fechamento }>("/api/condicoes", json(c)),
  resolverSinal: (s: { cnpj: string; texto: string; fonte: string; registrado_por: string }) =>
    pedir<{ fechamento: Fechamento }>("/api/sinais-resolvidos", json(s)),
  enviarArquivos: (arquivos: FileList | File[]) => {
    const form = new FormData();
    Array.from(arquivos).forEach((f) => form.append("arquivos", f));
    return pedir<Fechamento>("/api/arquivos", { method: "POST", body: form });
  },

  tratamentos: () => pedir<{ acoes: Tratamento[] }>("/api/tratamentos"),
  caso: (hash: string) => pedir<CasoDetalhe>(`/api/casos/${hash}`),
  precedentes: (hash: string) => pedir<{ precedentes: Decisao[] }>(`/api/casos/${hash}/precedentes`),
  propor: (corpo: Record<string, unknown>) =>
    pedir<Decisao>("/api/decisoes", json(corpo, true)),
  aprovar: (id: number, corpo: Record<string, unknown> = {}) =>
    pedir<{ decisao: Decisao; fechamento: Fechamento }>(`/api/decisoes/${id}/aprovar`, json(corpo, true)),
  rejeitar: (id: number, motivo: string) =>
    pedir<Decisao>(`/api/decisoes/${id}/rejeitar`, json({ motivo }, true)),
  revogar: (id: number, motivo: string) =>
    pedir<Decisao>(`/api/decisoes/${id}/revogar`, json({ motivo }, true)),
  registrarResultado: (caso_hash: string, corpo: Record<string, unknown>) =>
    pedir<{ id: number }>(`/api/casos/${caso_hash}/resultado`, json(corpo, true)),
  metricas: () => pedir<Record<string, unknown>>("/api/metricas"),
};
