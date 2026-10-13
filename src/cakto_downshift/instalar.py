"""Liga e desliga os hooks no settings.json do Claude Code. Usa json, não jq, e mexe só no que é
nosso: hook alheio fica, hook nosso antigo sai antes do novo entrar, e rodar duas vezes dá o mesmo."""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from cakto_downshift import escopo as mod_escopo
from cakto_downshift import perfil as mod_perfil

EVENTOS = (
    ("PreToolUse", "Task|Agent", "pre-tool-use"),
    ("PostToolUse", "Task|Agent", "post-tool-use"),
    ("PostToolUseFailure", "Task|Agent", "post-tool-use"),
    ("SubagentStop", None, "subagent-stop"),
    ("SessionStart", None, "session-start"),
)


def comando_hook(executavel: Path, nome: str) -> str:
    return f'"{executavel}" hook {nome}'


def e_nosso(comando: str) -> bool:
    return "cakto-downshift" in comando and " hook " in comando


def _sem_os_nossos(grupos: list) -> list:
    saida = []
    for g in grupos:
        hooks = [h for h in g.get("hooks", []) if not e_nosso(h.get("command", ""))]
        if hooks:
            saida.append({**g, "hooks": hooks})
    return saida


def remover(settings: dict) -> dict:
    novo = json.loads(json.dumps(settings))
    hooks = {ev: _sem_os_nossos(gs) for ev, gs in (novo.get("hooks") or {}).items()}
    novo["hooks"] = {ev: gs for ev, gs in hooks.items() if gs}
    return novo


def mesclar(settings: dict, executavel: Path) -> dict:
    novo = remover(settings)
    for evento, matcher, nome in EVENTOS:
        grupo = {"hooks": [{"type": "command", "command": comando_hook(executavel, nome), "timeout": 10}]}
        if matcher:
            grupo = {"matcher": matcher, **grupo}
        novo["hooks"].setdefault(evento, []).append(grupo)
    return novo


def _ler(settings_path: Path) -> dict:
    try:
        return json.loads(settings_path.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _escrever(settings_path: Path, dados: dict) -> list[str]:
    feitos = []
    texto = json.dumps(dados, indent=2, ensure_ascii=False) + "\n"
    if settings_path.exists():
        alvo = settings_path.resolve()
        backup = alvo.with_name(f"{alvo.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(alvo, backup)
        feitos.append(f"backup em {backup}")
        modo = alvo.stat().st_mode & 0o777
        # Escrever através do link mantém o dotfile de quem usa symlink; mode preservado em seguida.
        settings_path.write_text(texto, encoding="utf-8")
        os.chmod(alvo, modo)
    else:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(texto, encoding="utf-8")
        feitos.append(f"criado {settings_path}")
    return feitos


def plano(settings_path: Path, home: Path, escopo: Path | None, executavel: Path) -> str:
    atual = _ler(settings_path)
    novo = mesclar(atual, executavel)
    linhas = [f"settings: {settings_path}", f"escopo: {escopo or 'qualquer pasta'}",
              f"perfil: {'mantido' if mod_perfil.caminho(home).exists() else 'criado em medium'}", "hooks depois:"]
    for ev, gs in novo["hooks"].items():
        for g in gs:
            for h in g["hooks"]:
                marca = "novo" if e_nosso(h["command"]) else "mantido"
                linhas.append(f"  {ev}: {h['command']} ({marca})")
    linhas.append("Nada foi alterado. Rode de novo com --aplicar.")
    return "\n".join(linhas)


def aplicar(settings_path: Path, home: Path, escopo: Path | None, executavel: Path) -> list[str]:
    feitos = []
    if escopo is not None:
        mod_escopo.salvar(home, escopo)
        feitos.append(f"escopo: {escopo.resolve()}")
    if not mod_perfil.caminho(home).exists():
        # Só cria: o perfil é escolha de quem usa, e reinstalar não pode desfazer um `economia alta`.
        mod_perfil.salvar(home, mod_perfil.Perfil())
        feitos.append("perfil criado em medium")
    feitos += _escrever(settings_path, mesclar(_ler(settings_path), executavel))
    feitos.append("hooks escritos; valem na próxima sessão do Claude Code")
    return feitos


def desinstalar(settings_path: Path) -> list[str]:
    if not settings_path.exists():
        return ["settings não existe; nada a fazer"]
    return _escrever(settings_path, remover(_ler(settings_path))) + ["hooks removidos; o estado em ~/.cakto-downshift ficou"]
