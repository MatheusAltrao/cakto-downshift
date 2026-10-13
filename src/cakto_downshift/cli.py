"""Linha de comando. Os hooks são `hook <nome>`; o resto é operação do dev."""
import argparse
import json
import os
import sys
from pathlib import Path

from cakto_downshift import __version__
from cakto_downshift import escopo as mod_escopo
from cakto_downshift import perfil as mod_perfil
from cakto_downshift.catalogo import familia_de
from cakto_downshift.piso import carregar_do_projeto
from cakto_downshift.politica import Entrada, decidir

TEXTO_ECONOMIA = """\
low     qualidade primeiro: nada vai para o Haiku; até 6 subagentes
medium  padrão; até 4 subagentes
high    tarefa sem sinal claro desce de Opus para Sonnet (nunca Haiku, nunca com risco); até 2 subagentes"""


def home() -> Path:
    return Path(os.environ.get("CAKTO_DOWNSHIFT_HOME") or Path.home() / ".cakto-downshift")


def settings_path() -> Path:
    return Path(os.environ.get("CAKTO_DOWNSHIFT_SETTINGS") or Path.home() / ".claude" / "settings.json")


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cakto-downshift", description="O brain pensa; este economiza.")
    parser.add_argument("--version", action="version", version=f"cakto-downshift {__version__}")
    sub = parser.add_subparsers(dest="comando")

    hook = sub.add_parser("hook", help="executa um hook do Claude Code lendo o JSON do stdin")
    hook.add_argument("nome")

    t = sub.add_parser("try", help="o que o hook faria com este texto")
    t.add_argument("texto")
    t.add_argument("--modelo-atual", default="opus")
    t.add_argument("--agente", default="general-purpose")
    t.add_argument("--projeto", default=None, help="pasta de onde procurar o piso (padrão: cwd)")

    e = sub.add_parser("economia", help="perfil de economia e orçamento de subagentes", epilog=TEXTO_ECONOMIA,
                       formatter_class=argparse.RawDescriptionHelpFormatter)
    e.add_argument("args", nargs="*")

    st = sub.add_parser("stats", help="decisões, usos e economia estimada")
    st.add_argument("--dias", type=int, default=7)

    sub.add_parser("doctor", help="estado da instalação")

    ins = sub.add_parser("instalar", help="registra os hooks no settings.json do Claude Code")
    ins.add_argument("--escopo", default=None, help="pasta onde o hook age (padrão: qualquer pasta)")
    ins.add_argument("--aplicar", action="store_true", help="escreve de verdade; sem isso só mostra o plano")

    des = sub.add_parser("desinstalar", help="remove os hooks do settings.json")
    des.add_argument("--aplicar", action="store_true", help="escreve de verdade; sem isso nada muda")
    return parser


def cmd_try(args) -> int:
    raiz = Path(args.projeto or os.getcwd())
    piso, erro = carregar_do_projeto(raiz)
    d = decidir(Entrada(args.texto, familia_de(args.modelo_atual), args.agente, mod_perfil.carregar(home()), piso))
    print(f"classe:      {d.classe.name.lower()} ({'com' if d.confianca else 'sem'} confiança)")
    print(f"risco:       {', '.join(sorted(r.value for r in d.riscos)) or 'nenhum'}")
    print(f"tier:        {d.tier.name.lower()}")
    print(f"modelo:      {d.familia_atual or 'desconhecido'} → {d.familia_escrita or 'sem mudança'}")
    print(f"motivos:     {' '.join(d.motivos)}")
    if erro:
        print(f"piso:        ignorado, inválido: {erro}")
    return 0


def cmd_economia(args) -> int:
    p = mod_perfil.carregar(home())
    a = args.args
    if not a:
        pass
    elif len(a) == 1:
        econ = mod_perfil.interpretar_economia(a[0])
        if econ is None:
            print(f"perfil inválido: {a[0]!r}\n{TEXTO_ECONOMIA}", file=sys.stderr)
            return 2
        p.economia = econ
    elif len(a) == 2 and a[0] == "subagentes":
        if a[1] == "auto":
            p.max_subagentes = None
        elif a[1].isdigit() and 1 <= int(a[1]) <= mod_perfil.MAX_SUBAGENTES_ABSOLUTO:
            p.max_subagentes = int(a[1])
        else:
            print(f"valor inválido: {a[1]!r} (inteiro entre 1 e {mod_perfil.MAX_SUBAGENTES_ABSOLUTO}, ou auto)", file=sys.stderr)
            return 2
    elif len(a) == 2 and a[0] == "gb":
        try:
            gb = None if a[1] == "auto" else float(a[1])
        except ValueError:
            gb = -1.0
        if gb is not None and not 0.5 <= gb <= 64:
            print(f"valor inválido: {a[1]!r} (número entre 0.5 e 64, ou auto)", file=sys.stderr)
            return 2
        p.gb_por_subagente = mod_perfil.GB_PADRAO if gb is None else gb
    else:
        print("uso: cakto-downshift economia [low|medium|high] | subagentes <N|auto> | gb <N|auto>", file=sys.stderr)
        return 2
    if a:
        mod_perfil.salvar(home(), p)
    orc = mod_perfil.orcamento(p, mod_perfil.ram_disponivel_gb())
    print(f"economia:    {p.economia.value}")
    print(f"subagentes:  {orc.maximo} em paralelo (teto do perfil {orc.teto}, motivo: {orc.motivo})")
    print(f"memória:     {f'{orc.ram_gb:.1f} GB disponíveis' if orc.ram_gb else 'desconhecida'}, {orc.gb_por_subagente:.1f} GB por subagente")
    print(f"arquivo:     {mod_perfil.caminho(home())}")
    if a:
        print("O perfil vale no próximo subagente; o orçamento, na próxima sessão do Claude Code.")
    return 0


def cmd_doctor() -> int:
    h = home()
    print(f"versão:      {__version__}")
    print(f"home:        {h} ({'existe' if h.is_dir() else 'ausente'})")
    esc = mod_escopo.carregar(h)
    print(f"escopo:      {esc or 'qualquer pasta'}")
    p = mod_perfil.carregar(h)
    print(f"perfil:      {p.economia.value}, modelos {list(p.modelos)}")
    try:
        hooks = json.loads(settings_path().read_text(encoding="utf-8")).get("hooks", {})
        for evento, grupos in hooks.items():
            n = sum(1 for g in grupos for hk in g.get("hooks", []) if "cakto-downshift" in hk.get("command", ""))
            if n:
                print(f"hook {evento}: {n}")
    except (OSError, ValueError, AttributeError):
        print(f"hooks:       {settings_path()} não lido")
    piso, erro = carregar_do_projeto(Path(os.getcwd()))
    if erro:
        print(f"piso:        inválido, ignorado: {erro}")
    else:
        print(f"piso:        {'encontrado' if piso else 'nenhum'} a partir de {os.getcwd()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = construir_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    if args.comando == "hook":
        from cakto_downshift.hooks.claude_code import executar
        return executar(args.nome, sys.stdin.buffer, sys.stdout, os.environ)
    if args.comando == "try":
        return cmd_try(args)
    if args.comando == "economia":
        return cmd_economia(args)
    if args.comando == "stats":
        from datetime import datetime, timedelta, timezone
        from cakto_downshift.stats import formatar, resumo
        from cakto_downshift.telemetria import ler
        desde = datetime.now(timezone.utc) - timedelta(days=args.dias)
        print(formatar(resumo(ler(home(), desde)), args.dias))
        return 0
    if args.comando == "doctor":
        return cmd_doctor()
    if args.comando in ("instalar", "desinstalar"):
        from cakto_downshift import instalar as mod_instalar
        exe = Path(sys.argv[0]).resolve() if Path(sys.argv[0]).name == "cakto-downshift" else Path(sys.executable).with_name("cakto-downshift")
        if args.comando == "instalar":
            escopo = Path(args.escopo).resolve() if args.escopo else None
            if escopo and not escopo.is_dir():
                print(f"pasta do --escopo não existe: {escopo}", file=sys.stderr)
                return 2
            try:
                if not args.aplicar:
                    print(mod_instalar.plano(settings_path(), home(), escopo, exe))
                    return 0
                print("\n".join(mod_instalar.aplicar(settings_path(), home(), escopo, exe)))
            except ValueError as e:
                print(str(e), file=sys.stderr)
                return 1
            return 0
        if not args.aplicar:
            print("sem --aplicar nada muda; os hooks atuais estão em", settings_path())
            return 0
        try:
            print("\n".join(mod_instalar.desinstalar(settings_path())))
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
