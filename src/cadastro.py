"""Cadastro de lojistas: EC Orbe -> CNPJ (chave exata) e taxa contratada vigente numa data.

Nenhum casamento por nome. O EC vem da coluna 'EC Orbe' da planilha ou do de-para explícito
de premissas.json (respostas do financeiro). O resto vira pendência.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.leitura import LinhaOrbe, LinhaTaxa


class Cadastro:
    def __init__(self, linhas: list[LinhaTaxa], premissas: dict):
        self.linhas = linhas
        self.ec_para_cnpj: dict[str, str] = {}
        self.origem_ec: dict[str, str] = {}
        self.nome: dict[str, str] = {}
        for lt in linhas:
            if lt.cnpj and lt.cnpj not in self.nome:
                self.nome[lt.cnpj] = lt.lojista
            if lt.ec and lt.cnpj:
                self._vincular(lt.ec, lt.cnpj, f"planilha linha {lt.linha_planilha}")
        for ec, item in premissas.get("de_para_ec", {}).items():
            if item["cnpj"] not in self.nome:
                raise ValueError(f"de-para do EC {ec}: CNPJ {item['cnpj']} não está na planilha")
            self._vincular(ec, item["cnpj"], item["fonte"])
        self.isencoes = [
            (i["cnpj"], date.fromisoformat(i["inicio"]), date.fromisoformat(i["fim"]), i["fonte"])
            for i in premissas.get("isencoes", [])
        ]

    def _vincular(self, ec: str, cnpj: str, origem: str) -> None:
        atual = self.ec_para_cnpj.get(ec)
        if atual and atual != cnpj:
            raise ValueError(f"EC {ec} ligado a dois CNPJs: {atual} e {cnpj} ({origem})")
        self.ec_para_cnpj[ec] = cnpj
        self.origem_ec.setdefault(ec, origem)

    def motivo_sem_vinculo(self, ec: str) -> str:
        if any(lt.ec == ec for lt in self.linhas):
            return "EC aparece na planilha, mas a linha não tem CNPJ legível"
        return "EC não aparece na aba 'Taxas vigentes' nem no de-para confirmado pelo financeiro"

    def taxa(self, cnpj: str, chave: str, dia: date) -> tuple[Decimal | None, str]:
        """Taxa contratada (fração) vigente no dia, e a origem dela. (None, motivo) se não houver uma só."""
        for c, ini, fim, fonte in self.isencoes:
            if c == cnpj and ini <= dia <= fim:
                return Decimal("0"), f"isenção {fonte.split(':')[0]}"
        candidatas = [
            lt for lt in self.linhas
            if lt.cnpj == cnpj and lt.vigencia is not None
            and (lt.vigencia[0] is None or lt.vigencia[0] <= dia)
            and (lt.vigencia[1] is None or dia <= lt.vigencia[1])
        ]
        if len(candidatas) != 1:
            return None, f"{len(candidatas)} linhas de taxa vigentes em {dia:%d/%m/%Y}"
        taxa = candidatas[0].taxas.get(chave)
        if taxa is None:
            return None, f"taxa {chave} vazia na planilha linha {candidatas[0].linha_planilha}"
        return taxa, f"planilha linha {candidatas[0].linha_planilha}"


def chave_taxa(linha: LinhaOrbe) -> str | None:
    """Qual coluna da planilha vale para a linha da Orbe."""
    if linha.tipo in ("ANTECIPACAO", "REVERSAO ANTECIPACAO"):
        return "ANTECIPACAO"
    if linha.modalidade == "DEBITO":
        return "DEBITO"
    if linha.modalidade == "PIX":
        return "PIX"
    if linha.modalidade == "CREDITO A VISTA":
        return "CREDITO_VISTA"
    if linha.modalidade == "CREDITO PARCELADO" and linha.parcelas:
        if 2 <= linha.parcelas <= 6:
            return "CREDITO_2_6"
        if 7 <= linha.parcelas <= 12:
            return "CREDITO_7_12"
    return None
