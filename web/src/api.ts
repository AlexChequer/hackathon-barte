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
}

export interface Bloqueio {
  frente: string;
  faltando: string[];
  parcial: boolean;
  nao_sai: string;
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

async function pedir<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}));
    throw new Error(typeof corpo.detail === "string" ? corpo.detail : `Erro ${r.status} em ${url}`);
  }
  return r.json() as Promise<T>;
}

const json = (corpo: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
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
};
