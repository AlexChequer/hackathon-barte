const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const num = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const dinheiro = (v: string | number | null | undefined) => (v == null ? "—" : brl.format(Number(v)));
export const decimal = (v: string | number | null | undefined) => (v == null ? "—" : num.format(Number(v)));
export const pct = (v: string | null | undefined) => (v == null ? "—" : `${num.format(Number(v))}%`);

export const cnpj = (v: string | null | undefined) =>
  v && /^\d{14}$/.test(v) ? v.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5") : (v ?? "—");

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
export const competencia = (c: string) => `${MESES[Number(c.slice(5, 7)) - 1]} de ${c.slice(0, 4)}`;
export const data = (iso: string | null | undefined) => (iso ? iso.split("-").reverse().join("/") : "—");

export const MODALIDADES: Record<string, string> = {
  debito: "Débito",
  credito_vista: "Crédito à vista",
  credito_2a6: "Crédito 2–6x",
  credito_7a12: "Crédito 7–12x",
  pix: "Pix",
  antecipacao: "Antecipação",
};

export const TIPO_PENDENCIA: Record<string, string> = {
  CONTESTACAO_ORBE: "Contestar com a Orbe",
  CONDICAO_NAO_INFORMADA_ORBE: "Devolver ao lojista",
  CONDICAO_ESPECIAL_A_CONFIRMAR: "Condição especial a confirmar",
  SEM_CONTRATO: "Lojista sem contrato",
  ALERTA_ANTECIPACAO: "Antecipação acima das vendas",
  NOTA_NEGATIVA: "Comissão negativa, sem nota",
  SPREAD_NEGATIVO_CONTESTAR: "Spread negativo: contestar com a Ponte",
  CONTESTACAO_PONTE: "Contestar com a Ponte",
  DUPLICATA_RELATORIO_PONTE: "Duplicata no relatório da Ponte",
  LOJISTA_REMESSA_SEM_CADASTRO: "Lojista da Ponte sem cadastro",
  DIFERENCA_RELATORIO_PONTE: "Conferir o repasse da Ponte",
  PIX_NAO_IDENTIFICADO: "PIX sem identificação",
  DEVOLUCAO_LOJISTA_SEM_MOTIVO: "Devolução sem motivo",
  TRANSFERENCIA_EM_TRANSITO: "Transferência em trânsito",
  FRENTE_BLOQUEADA: "Parte do fechamento bloqueada",
};
export const tipoPendencia = (t: string | null) => (t && TIPO_PENDENCIA[t]) || (t ?? "").replaceAll("_", " ").toLowerCase();

export const FRENTE: Record<string, string> = { checkout: "Checkout", remessa: "Remessa", extratos: "Extratos" };
export const ARQUIVO: Record<string, string> = {
  orbe: "Relatório da Orbe",
  taxas: "Tabela de taxas contratadas",
  ponte: "Relatório de remessas (Ponte Câmbio)",
  plano: "Plano de contas",
  aurora: "Extrato Aurora",
  meridiano: "Extrato Meridiano",
};
