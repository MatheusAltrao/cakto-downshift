# cakto-downshift

O brain pensa; este economiza. É um hook do Claude Code que troca o modelo de cada subagente pelo
menor que dá conta da tarefa, sem chamar LLM nenhum para decidir. A sessão principal não muda, e
na dúvida o spawn segue como estava. Python 3.11+, só biblioteca padrão, sem chamada de rede.
Desenho completo em `docs/superpowers/specs/2026-10-12-cakto-downshift-design.md`.

## Instalar

```bash
python3 -m venv ~/.cakto-downshift/venv
~/.cakto-downshift/venv/bin/pip install git+https://github.com/MatheusAltrao/cakto-downshift
~/.cakto-downshift/venv/bin/cakto-downshift instalar --escopo ~/Documentos/codigos/trabalho/cakto
~/.cakto-downshift/venv/bin/cakto-downshift instalar --escopo ~/Documentos/codigos/trabalho/cakto --aplicar
~/.cakto-downshift/venv/bin/cakto-downshift doctor
```

`instalar` sem `--aplicar` só mostra o plano. Com `--aplicar` grava o escopo, cria o `perfil.json`
em `medium` (se não existir) e escreve os hooks no `~/.claude/settings.json`, com backup datado,
sem mexer em hooks alheios e sem duplicar se rodar de novo. Os hooks valem **na próxima sessão** do
Claude Code. O hook só age em projetos sob o escopo; sem `--escopo`, age em qualquer pasta.
`desinstalar --aplicar` tira os hooks e deixa o estado em `~/.cakto-downshift/`. Para atualizar:
`pip install --upgrade git+...` no mesmo venv.

Para ver o que o hook faria sem abrir sessão: `cakto-downshift try "renomeie a variável x" --modelo-atual opus`.

## Perfis de economia

| | `low` | `medium` (padrão) | `high` |
|---|---|---|---|
| Haiku | nunca | com confiança | com confiança |
| Tarefa sem confiança numa sessão Opus | fica | fica | desce para Sonnet, se não for complexa nem tiver risco |
| Teto de subagentes em paralelo | 6 | 4 | 2 |

```bash
cakto-downshift economia              # mostra o perfil e o orçamento
cakto-downshift economia high         # troca (aceita low|baixa, medium|media, high|alta)
cakto-downshift economia subagentes 3 # fixa o orçamento; "auto" volta ao cálculo
cakto-downshift economia gb 3         # GB de RAM por subagente (padrão 2)
```

O perfil é lido a cada spawn: a troca vale no próximo subagente. Nenhum perfil desliga as guardas:
tarefa complexa ou com risco nunca é rebaixada, e modelo desconhecido ou agente nomeado nunca é
reescrito.

## Orçamento de subagentes

`min(teto do perfil, RAM disponível ÷ GB por subagente)`, nunca abaixo de 1; `economia subagentes N`
fixa o valor. A RAM vem de `/proc/meminfo` (`MemAvailable`) no Linux e metade da física no macOS;
desconhecida, vale o teto. O número chega à sessão como contexto no `SessionStart`, com o motivo
e a orientação de agrupar tarefas pequenas. **É orientação, não trava**: um hook vê um spawn por vez
e não decide quantos filhos o modelo abre.

## Piso por repositório

Um `cakto-downshift.json` na raiz do repo (procurado de baixo para cima, até 8 níveis) define o
tier mínimo por classe ou por categoria de risco. Só sobe: nunca rebaixa. Arquivo inválido é
ignorado e o `doctor` avisa. Dois templates prontos em `docs/pisos/`:

- `pagamentos.json`: dinheiro, segredo, cripto e destrutivo em opus. Para `cakto-backend` e `cakto-split`.
- `front.json`: segredo e destrutivo em opus; dinheiro, acesso, dado pessoal, cripto e manipulação no
  mínimo sonnet. Para `cakto-frontend`, `cakto-checkout`, `cakto-checkout-v2`, `split-admin` e upsell
  (no checkout quase todo componente cita pix ou cartão; com dinheiro em opus nada sairia dali).

## Risco

Sete categorias (`dinheiro`, `dado_pessoal`, `segredo`, `acesso`, `cripto`, `destrutivo`,
`manipulacao`), com vocabulário em português e inglês, lido com e sem acento. Há dois tipos de termo:
**comportamento**, que vale sozinho (chargeback, estorno, `rm -rf`, CPF), e **substantivo com
contexto**, que só vale perto de uma palavra de dinheiro ou de banco (pix, boleto, tabela, coluna).
Risco é piso: a tarefa vai para Sonnet no mínimo e nunca desce para Haiku.

## Telemetria

Fica em `~/.cakto-downshift/eventos.jsonl` (pasta `0700`, arquivo `0600`), local, sem rede.

- **Grava:** quatro tipos de evento, `decisao` (classe, confiança, risco, perfil, modelo atual e
  escrito, códigos de motivo, milissegundos), `resultado` (modelo que o Claude Code reportou e como o
  filho terminou), `uso` (tokens de entrada, saída e cache do filho, custo pelo catálogo) e `falha`.
  A sessão vai como hash SHA-256 truncado e o projeto como o nome da pasta.
- **Nunca grava:** o texto do prompt, o caminho completo, o `session_id` cru, nem conteúdo do transcript.

## Ler o `stats`

`cakto-downshift stats --dias 7` mostra decisões por classe e tier, reescritas aplicadas (confirmadas
pelo `resultado`) e seguradas por motivo, custo real por tier e a economia estimada: o custo real dos
tokens do filho menos o custo dos mesmos tokens no modelo que ele teria herdado. **Toda economia é
estimada pelo catálogo, não é fatura**: os preços vêm de `catalogo.py` e atualizar preço é PR. Sem
custo ligado a uma decisão, o `stats` diz `sem dado` em vez de inventar número. Meça uma semana antes
de afirmar economia.

## Limitações conhecidas

- **`allow` nos spawns reescritos.** O Claude Code exige `permissionDecision` junto do `updatedInput`;
  então uma regra `ask` em `Task` é pulada nos spawns que o roteador muda. Spawn sem mudança responde
  `{}` e as regras do usuário valem.
- **Agente nomeado fica fora do roteador por padrão**, exceto quando a chamada traz `model`. Quem
  quiser roteá-los define `CAKTO_DOWNSHIFT_ROTEAR_NOMEADOS=1`. O ganho nos nomeados vem do `model:` no
  frontmatter: veja `docs/agentes.md`.
- **Ligação de custo por ordem.** O `SubagentStop` não traz o id da chamada; o custo é casado com a
  decisão mais recente da mesma sessão sem uso (até 2 horas). Com filhos em paralelo as pontas podem
  trocar, e o `stats` marca essas ligações como `ordem`.
- **Só os primeiros 16 KiB** do texto da tarefa são classificados.
- Só Claude Code; fail-open: qualquer falha do hook responde `{}` com exit 0 e grava um evento `falha`.

## Origem

Inspirado no downshift de Tiago Vilas Boas (Apache 2.0), lido e não copiado; este projeto é escrito do zero para a Cakto.
