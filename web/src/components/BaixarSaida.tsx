import { Download } from "lucide-react";
import { competencia as nomeCompetencia } from "../format";

const ARQUIVOS = [
  "comissoes_por_lojista.csv",
  "divergencias_taxa.csv",
  "notas_a_emitir.csv",
  "lancamentos_classificados.csv",
  "pendencias.csv",
  "rastro.csv",
];

/** Baixar os 6 CSVs do fechamento que está na tela, exatamente como foram gravados em saida/. */
export function BaixarSaida({ competencia }: { competencia: string }) {
  return (
    <section className="mt-10 border-t border-linha-forte pt-6">
      <h3 className="text-[15px] font-semibold">Baixar a saída</h3>
      <p className="mt-1 max-w-[68ch] text-sm text-tinta-2">
        Os 6 arquivos do fechamento de {nomeCompetencia(competencia)}, no formato pedido pela Tarvo (CSV com ponto e
        vírgula), iguais aos gravados em <span className="font-mono">saida/</span>.
      </p>
      <a
        href="/api/saida.zip"
        download
        className="mt-4 inline-flex items-center gap-2 rounded-lg border border-decisao bg-decisao-fundo px-4 py-2 text-sm font-medium text-decisao-tinta hover:bg-decisao/20"
      >
        <Download size={16} /> Baixar os 6 CSVs (.zip)
      </a>
      <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm">
        {ARQUIVOS.map((nome) => (
          <li key={nome}>
            <a href={`/api/saida/${nome}`} download className="font-mono text-tinta-2 underline-offset-2 hover:text-tinta hover:underline">
              {nome}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
