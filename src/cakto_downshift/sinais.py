"""Sinais ponderados. Peso 3 é um termo que sozinho define a classe; 1 é um indício.

Linha nova aqui exige um caso em tests/golden/classes.jsonl. PT-BR primeiro, EN depois.
"""
from dataclasses import dataclass

from cakto_downshift.classes import Classe


@dataclass(frozen=True)
class Sinal:
    padrao: str
    peso: int
    classe: Classe


M, S, ME, C = Classe.MECANICA, Classe.SIMPLES, Classe.MEDIA, Classe.COMPLEXA

SINAIS: tuple[Sinal, ...] = (
    # --- mecânica: a tarefa cabe numa substituição ---
    Sinal(r"\b(renomei\w*|renomear|rename|renaming)\b", 3, M),
    # "format" solto só vale no início: formatDate normaliza para "format date" e não é pedido de formatação.
    Sinal(r"\b(formate|formatar|prettier|lint|indent\w*)\b|^\W*format\b", 3, M),
    Sinal(r"\b(typo|erro de digitacao|ortografia)\b", 3, M),
    Sinal(r"^\W*(liste|listar|mostre|exiba|imprima|list|show|print)\b", 2, M),
    Sinal(r"\b(mova|mover|move)\b.{0,40}\b(arquivo|pasta|componente|file|folder|directory)\b", 3, M),
    Sinal(r"\b(remova|remover|apague|delete|remove)\b.{0,40}\b(console\.log|print\(|comentario\w*|comment\w*|import\w* n[a]o usad\w*|unused import\w*|dead code|codigo morto)", 3, M),
    Sinal(r"\b(troque|trocar|altere|atualize|mude|bump|set|change)\b.{0,40}\b(versao|version|porta|port|timeout|titulo|title|label|constante|constant|padrao|default)\b", 2, M),
    Sinal(r"\bgit (status|log|diff|branch)\b", 2, M),
    # --- simples: uma unidade pequena e isolada ---
    Sinal(r"\b(escreva|crie|adicione|implemente|write|create|add)\b.{0,30}\b(funcao|function|helper|util\w*)\b", 2, S),
    Sinal(r"\b(teste unitario|unit test|test case|caso de teste)\b", 2, S),
    Sinal(r"^\W*(explique|explica|o que (e|faz)|qual a diferenca|explain|what does)\b", 2, S),
    Sinal(r"\b(valida\w*|validate\w*|parse\w*|converta|convert)\b.{0,20}\b(data|date|cpf|email|url|intervalo|range|string)\b", 1, S),
    # --- média: várias partes se tocando ---
    Sinal(r"\b(implemente|implementar|implement|adicione|add)\b.{0,40}\b(feature|funcionalidade|endpoint|tela|pagina|page|fluxo|flow|exportacao|export|integracao)\b", 2, ME),
    Sinal(r"\b(corrija|corrigir|conserte|fix)\b.{0,20}\b(o |a |the )?(bug|erro|falha|problema|issue)\b", 2, ME),
    Sinal(r"\b(refator\w*|refactor\w*|reestrutur\w*|restructure)\b", 2, ME),
    Sinal(r"\b(investig\w*|diagnostic\w*|debug\w*|por que .{0,30}(falha|quebra|erro)|why .{0,30}(fail|break))\b", 2, ME),
    Sinal(r"\b(revis\w*|review)\b", 2, ME),
    Sinal(r"\b(paginacao|pagination|cache|serializer|middleware|hook|componente|component|modulo|module)\b", 1, ME),
    # --- complexa: decisão de desenho ou falha entre camadas ---
    Sinal(r"\b(arquitetura|architecture|desenhe|design)\b", 3, C),
    Sinal(r"\b(migra(cao|coes|tion|tions)|migrar|migrate)\b", 3, C),
    Sinal(r"\b(race condition|concorren\w*|concurren\w*|deadlock|lock)\b", 3, C),
    Sinal(r"\b(causa raiz|root cause)\b", 3, C),
    Sinal(r"\b(seguranca|security|vulnerabilidade|vulnerability|pentest)\b", 3, C),
    Sinal(r"\b(distribu\w*|sem downtime|zero downtime|consisten\w*|idempoten\w*|retentativa|retry|fila|queue)\b", 2, C),
    Sinal(r"\b(entre (os|as|dois|duas|tres) (servicos|camadas|repositorios)|across .{0,20}services)\b", 2, C),
)
