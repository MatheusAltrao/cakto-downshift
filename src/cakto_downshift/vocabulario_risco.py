"""Vocabulário de risco. É a parte que o time mais edita, e cada termo novo vem com um caso no golden.

Dois tipos de termo. COMPORTAMENTOS valem sozinhos: a palavra já é a operação de risco.
SUBSTANTIVOS só valem com uma palavra de CONTEXTO a até DISTANCIA_CONTEXTO caracteres, dos dois
lados, porque "pix" também é um ícone e "coluna" também é um grid.
Padrões sem acento: o texto chega normalizado.
"""
from enum import Enum


class Categoria(str, Enum):
    DINHEIRO = "dinheiro"
    DADO_PESSOAL = "dado_pessoal"
    SEGREDO = "segredo"
    ACESSO = "acesso"
    CRIPTO = "cripto"
    DESTRUTIVO = "destrutivo"
    MANIPULACAO = "manipulacao"


DISTANCIA_CONTEXTO = 30

COMPORTAMENTOS: dict[Categoria, tuple[str, ...]] = {
    Categoria.DINHEIRO: (
        r"\bsaques?\b", r"\bestorn\w*", r"\breembols\w*", r"\brefunds?\b", r"\bchargebacks?\b",
        r"\bcontestac\w*", r"\bdisputes?\b", r"\brepasses?\b", r"\bliquidac\w*", r"\bsettlements?\b",
        r"\bconciliac\w*", r"\bantecipac\w*", r"\bantifraude\b", r"\btokenizac\w*", r"\bpayouts?\b",
        r"\bcobrad[oa]s? (duas|2|em dobro)", r"\bcobranca (duplicada|em dobro|indevida)",
        r"\bsplit (de|do|dos|entre) (pagamento|repasse|coprodut\w*|afiliad\w*|produtor\w*)",
        r"\bdouble[- ]charg\w*", r"\bpayment (flow|logic|processing|gateway)\b", r"\bbilling (cycle|logic)\b",
    ),
    Categoria.DADO_PESSOAL: (
        r"\bcpf\b", r"\bcnpj\b", r"\bkyc\b", r"\bdados (pessoais|sensiveis)\b", r"\bpersonal data\b",
        r"\blgpd\b", r"\bgdpr\b", r"\b(e-?mail|telefone|endereco) do (cliente|comprador|produtor|aluno)\b",
        r"\bdocumento de identidade\b", r"\bssn\b",
    ),
    Categoria.SEGREDO: (
        r"\bsenhas?\b", r"\bpasswords?\b", r"\bsecrets?\b", r"\bsegredos?\b", r"\bcredencia(l|is)\b",
        r"\bcredentials?\b", r"\bapi[ -]?keys?\b", r"\bchaves? (privada|secreta|de api|de acesso)s?\b",
        r"\bprivate keys?\b", r"\btokens? de (acesso|sessao|api)\b", r"\b(access|refresh|bearer) tokens?\b",
        r"\bjwts?\b", r"\boauth\w*", r"\b2fa\b", r"\bmfa\b", r"\btotp\b",
    ),
    Categoria.ACESSO: (
        r"\bpermiss(ao|oes)\b", r"\bpermissions?\b", r"\bprivilegios?\b", r"\bcontrole de acesso\b",
        r"\baccess control\b", r"\brbac\b", r"\bautentica\w*", r"\bautoriza\w*", r"\bauthenticat\w*",
        r"\bauthoriz\w*", r"\b(is )?admin (role|rights|access)\b", r"\bpapel de admin\w*",
        r"\b(pedidos?|dados|contas?|faturas?|carrinhos?|compras?) de outr[oa]s?\b",
        r"\b(ver|acessar|editar) .{0,30}de outr[oa]s? (usuario|cliente|comprador|produtor)\b",
        r"(^|[^/.\w-])auth([^/.\w-]|$)",
    ),
    Categoria.CRIPTO: (
        r"\bcriptograf\w*", r"\bencrypt\w*", r"\bdecrypt\w*", r"\bhmac\b", r"\btls\b", r"\bssl\b",
        r"\bassinaturas? (do webhook|de webhook|hmac|digita\w*)\b", r"\bwebhook signatures?\b",
        r"\b(verify|validate|valide|verifique) .{0,10}(the )?(signature|assinatura)\b", r"\bcertificados? digita\w*",
    ),
    Categoria.DESTRUTIVO: (
        r"\brm\s+-rf\b", r"\bdrop (table|database|schema|column)s?\b", r"\btruncate\b",
        r"\bforce[- ]push\b", r"\bpush\s+(-f|--force)\b", r"\breset\s+--hard\b", r"\bforcar (o )?push\b",
        r"\bbanco de (producao|prd)\b", r"\b(dados|base) de (producao|prd)\b", r"\bprod(uction)? (data|database|db)\b",
        r"\b(apag|exclu|delet|remov|limp|zer|trunc)\w*\b.{0,40}\b(do|no|da|na|de|em)\s+(banco|base de dados|database|postgres)\b",
        r"\b(apag|exclu|delet|remov|limp|trunc)\w*\b.{0,30}\b(tabelas?|colunas?|registros?|linhas?|dados)\b.{0,40}\b(banco|base de dados|database|postgres|migration|migracao|schema)\b",
        r"\bmigra(tion|cao)\b.{0,40}\b(remov|apag|drop|exclu|delet)\w*", r"\bdelete (all|every)\b", r"\bwipe\b",
    ),
    Categoria.MANIPULACAO: (
        r"\b(ignore|desconsidere|esqueca|disregard|forget)\b.{0,20}\b(instrucoes|regras|instructions|rules)\b",
        r"\b(isso|isto|esta tarefa|this) (e|is) (trivial|facil|easy|tiny)\b",
        r"\b(use|usa|mande|rode|route|send|run)\b.{0,30}\b(modelo|model|tier)?\s*(mais )?(barato|pequeno|cheap\w*|small\w*|haiku|mini|nano)\b",
        r"\bsystem prompt\b",
    ),
}

SUBSTANTIVOS: dict[Categoria, tuple[str, ...]] = {
    Categoria.DINHEIRO: (
        r"\bpix\b", r"\bboletos?\b", r"\bcart(ao|oes)\b", r"\bcards?\b", r"\bsaldos?\b", r"\bbalance\b",
        r"\bparcel\w*", r"\binstallments?\b", r"\bjuros\b", r"\btaxas?\b", r"\bfees?\b", r"\bcup(om|ons)\b",
        r"\bcoupons?\b", r"\bassinaturas?\b", r"\brecorrencias?\b", r"\bsubscriptions?\b", r"\bsplit\b",
        r"\badquirentes?\b", r"\bgateway\b", r"\b3ds\b", r"\bpaypal\b", r"\bebanx\b", r"\bworldpay\b", r"\bbraintree\b",
        r"\bstripe\b",
    ),
}

CONTEXTO: dict[Categoria, tuple[str, ...]] = {
    Categoria.DINHEIRO: (
        r"\bcalcul\w*", r"\blogica\b", r"\bfluxo\b", r"\bflow\b", r"\bprocess\w*", r"\bregra\b", r"\bvalida\w*",
        r"\bgera\w*", r"\bcobr\w*", r"\bcharg\w*", r"\bvalor(es)?\b", r"\bamount\b", r"\bliquid\w*",
        r"\bintegra\w*", r"\bwebhook\b", r"\bapi\b", r"\bestorn\w*", r"\bcaptur\w*", r"\bautoriza\w*",
        r"\bconfirma\w*", r"\btransac\w*", r"\bpagamentos?\b", r"\bpayments?\b", r"\bpagar\b", r"\bpag[oa]s?\b",
        r"\bdesconto\b", r"\bdiscount\b", r"\barredond\w*", r"\bround\w*", r"\blimite\b", r"\bduplic\w*",
        r"\bdebit\w*", r"\bcredit\w*", r"\brepass\w*", r"\bcomiss\w*", r"\bpercentual\b", r"\brecorrente\b",
        r"\bcancelad\w*", r"\baplicad\w*", r"\baprovad\w*", r"\brecusad\w*", r"\bplano\b", r"\btimes? out\b",
    ),
}
