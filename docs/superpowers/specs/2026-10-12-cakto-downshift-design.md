# cakto-downshift: desenho

Data: 2026-10-12. Autor: Matheus Altrao. Status: aprovado em conversa, aguardando revisão do texto. Só Claude Code nesta versão.

## 1. O que é

Um hook do Claude Code que troca o modelo de cada subagente pelo menor que dá conta da tarefa, sem
chamar LLM nenhum para decidir. A sessão principal não muda. Na dúvida, o spawn segue como estava.

O brain pensa; este economiza. Projeto da Cakto, escrito do zero em Python.

## 2. Por que existe

Na máquina de um dev do Payments, em 4 dias de outubro de 2026, 117 subagentes foram abertos a
partir de uma sessão em Opus. 59% das tarefas eram mecânicas (renomear, listar, formatar) e todas
rodaram no modelo mais caro, porque o filho herda o modelo do pai. Haiku 5.5 custa 40 vezes menos
que Opus 5.5 por token de entrada.

Três coisas que um roteador genérico erra na Cakto e que este acerta por desenho:

1. **O risco de pagamentos está em português.** "formate a data do relatório de chargeback" não é
   tarefa de Haiku, e a palavra que diz isso é "chargeback", não "payment".
2. **O acento quebra regex ASCII.** "revisão" e "segurança" precisam ser lidas com e sem acento, em
   NFC e NFD.
3. **O agente nomeado tem dono.** Quem escreveu `seguranca.md` com `model: opus` decidiu com
   contexto que o texto de uma tarefa não carrega.

## 3. Escopo da v1

Entra:
- hook `PreToolUse` em `Task|Agent`: classifica, aplica risco, piso e perfil, e reescreve o modelo;
- perfil de economia `low|medium|high` por máquina e orçamento de subagentes pela RAM, entregue como
  contexto no `SessionStart`;
- custo real por filho no `SubagentStop`, resultado do filho no `PostToolUse`, e `stats` que só
  afirma economia com dado ligado;
- piso por repositório num arquivo na raiz, que só sobe tier;
- instalador e desinstalador que mexem no `~/.claude/settings.json` com backup e sem duplicar;
- `try`, `doctor`, `economia`.

Fica de fora, de propósito: outros harnesses (Cursor, Codex, Kiro…), classificador aprendido,
memória de acertos, compressão de contexto, dashboard, qualquer chamada de rede.

## 4. Arquitetura

Pacote `cakto_downshift`, Python 3.11+, **zero dependência em runtime** (pytest só em dev). Um
subagente custa um processo Python por spawn; sem imports pesados o arranque fica em dezenas de
milissegundos.

```
cakto-downshift/
  pyproject.toml
  src/cakto_downshift/
    normalizar.py          minúsculas, sem acento (NFC e NFD), camelCase e snake_case abertos
    sinais.py              tabela de sinais ponderados por classe, PT-BR e EN
    classificador.py       texto → classe + pontuação + confiança
    vocabulario_risco.py   listas por categoria: comportamento e substantivo-com-contexto
    risco.py               texto → categorias de risco
    politica.py            classe + risco + perfil + piso + modelo atual → Decisao
    perfil.py              perfil.json, orçamento de subagentes pela RAM
    piso.py                cakto-downshift.json do repositório, só sobe
    catalogo.py            modelos Claude: id, família, tier, preço por milhão
    transcript.py          modelo da sessão e tokens de um transcript JSONL, sem guardar texto
    telemetria.py          eventos JSONL, sem prompt, sessão como hash
    escopo.py              a pasta onde o hook age
    hooks/claude_code.py   pre_tool_use, session_start, subagent_stop, post_tool_use
    cli.py                 try · economia · stats · doctor · instalar · desinstalar · hook <nome>
  tests/
  docs/
```

**Regras de dependência entre módulos:** `classificador`, `risco` e `politica` não leem disco nem
ambiente; recebem tudo por parâmetro e devolvem valores. Só `perfil`, `piso`, `telemetria`,
`escopo`, `transcript` e `hooks` tocam o sistema. Isso é o que torna o golden set um teste puro.

**Estado em `~/.cakto-downshift/`** (`0700`, arquivos `0600`): `venv/`, `perfil.json`, `escopo`,
`eventos.jsonl`. Variável `CAKTO_DOWNSHIFT_HOME` troca a pasta, para testes e para quem quiser.

## 5. Fluxo do hook principal

Entrada (stdin, JSON do Claude Code): `session_id`, `cwd`, `transcript_path`, `tool_name`,
`tool_use_id`, `tool_input` com `prompt`, `description`, `subagent_type`, `model`.

1. **Escopo.** Se a raiz do projeto (`CLAUDE_PROJECT_DIR`, senão `cwd`) não está sob a pasta
   gravada em `escopo`, responde `{}` e sai. Sem escopo gravado, age em qualquer pasta.
2. **Texto da tarefa:** `prompt`, senão `description`. Vazio: `{}`.
3. **Modelo atual:** o `model` da chamada; senão o `model` da última mensagem `assistant` do
   `transcript_path` (lendo só o fim do arquivo); senão desconhecido.
4. **Classifica** (seção 6), **aplica risco** (seção 7), **piso do repo** (seção 9), **perfil**
   (seção 8), e **guardas** (seção 10). Sai uma `Decisao`.
5. **Resposta:**
   - sem escrita: `{}`. Nenhuma `permissionDecision`: as regras de permissão do usuário valem.
   - com escrita: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision":
     "allow", "updatedInput": {...tool_input, "model": "<família>"}}}`. O Claude Code aceita só
     nomes de família (`haiku`, `sonnet`, `opus`, `fable`) e exige a decisão junto do input.
     **Limitação documentada:** uma regra `ask` em `Task` é pulada nos spawns que o roteador muda.
6. **Telemetria:** uma linha `decisao` (seção 11), com os milissegundos gastos.

**Fail-open em tudo.** Exceção de qualquer tipo, JSON inválido, stdin vazio ou acima de 1 MB,
transcript ilegível: responde `{}`, exit 0, e grava um evento `falha`. O hook nunca sai com código
diferente de 0 e nunca faz chamada de rede. **Meta de latência:** menos de 150 ms por spawn, teste
com 200 spawns e com um prompt de 1 MB.

## 6. Classificação

Quatro classes, três tiers:

| Classe | O que é | Tier |
|---|---|---|
| `mecanica` | renomear, formatar, listar, corrigir typo, mover arquivo | haiku |
| `simples` | função pequena e isolada, explicar um trecho, teste unitário de uma função | haiku |
| `media` | feature em mais de um arquivo, bug com causa a investigar, refactor de módulo | sonnet |
| `complexa` | arquitetura, migração, concorrência, segurança, causa raiz entre camadas | opus |

O texto normalizado passa pela tabela de `sinais.py`: cada sinal é uma regex, um peso de 1 a 3 e
uma classe. Soma por classe; vence a maior; empate vai para a mais alta. **Confiança** é verdadeira
quando a margem entre a primeira e a segunda classe é de pelo menos 2 pontos **e**, para
`mecanica` e `simples`, o prompt tem no máximo 40 palavras (um brief longo com um "renomeie" está
descrevendo trabalho que a palavra não cobre). Sem sinal nenhum: `media`, sem confiança.

A tabela é escrita por nós, em PT-BR primeiro e EN depois, com verbos e objetos do dia a dia da
Cakto (card, checkout, split, migration, serializer, componente, hook). Cada linha nova da tabela
vem com um caso no golden set.

## 7. Risco

Sete categorias: `dinheiro`, `dado_pessoal`, `segredo`, `acesso`, `cripto`, `destrutivo`,
`manipulacao`. Cada uma tem dois tipos de termo em `vocabulario_risco.py`:

- **comportamento**, vale sozinho: saque, estorno, reembolso, chargeback, contestação, repasse,
  liquidação, conciliação, antecipação, antifraude, tokenização, `rm -rf`, `drop table`, "banco de
  produção", senha, chave privada, token de acesso, CPF, CNPJ, KYC, "pedido de outro cliente";
- **substantivo com contexto**, só vale com uma palavra de dinheiro ou de banco a até 30
  caracteres de distância, dos dois lados: pix, boleto, cartão, saldo, parcela, juros, taxa, cupom,
  assinatura, recorrência, tabela, coluna, registro. As palavras de contexto são verbos e nomes de
  dinheiro (calcular, cobrar, valor, desconto, liquidar, estornar, pagamento, transação…) e de
  banco (banco, base, migration, schema, produção).

Sem contexto, "mude a cor do ícone do pix" e "remova as colunas vazias do CSV" são UI e texto, e
vão para o Haiku. `manipulacao` cobre o prompt que tenta dirigir o roteador ("isso é trivial",
"use o modelo mais barato", "ignore as instruções anteriores").

**Risco é piso:** a classe sobe para `media` no mínimo, perde a confiança, e a tarefa nunca é
rebaixada. O golden set de risco tem duas listas: o que tem de entrar e o que tem de ficar de fora,
e as duas rodam no CI.

## 8. Perfil de economia

`~/.cakto-downshift/perfil.json`:
`{"economia": "medium", "max_subagentes": null, "gb_por_subagente": 2, "modelos": ["haiku", "sonnet", "opus"]}`.
`modelos` é a lista de famílias que o hook pode escrever, da mais barata para a mais cara; quem
quiser o upshift até o Fable acrescenta `"fable"` no fim.
Comando `economia` mostra e troca; nomes aceitos em qualquer caixa: `low|baixa`, `medium|media`,
`high|alta`.

| | `low` | `medium` (padrão) | `high` |
|---|---|---|---|
| Haiku | nunca | com confiança | com confiança |
| Tarefa sem confiança numa sessão Opus | fica | fica | desce para Sonnet, se não for complexa nem tiver risco |
| Teto de subagentes em paralelo | 6 | 4 | 2 |

O piso do `low` tem flag própria (`piso_perfil`) e **não isenta guarda nenhuma**. Em especial: um
spawn em que o `medium` não escreveria nada (modelo atual desconhecido, agente nomeado) continua sem
escrita no `low`. O hook lê o perfil a cada spawn; a troca vale no próximo subagente.

**Orçamento de subagentes:** `min(teto do perfil, RAM disponível ÷ gb_por_subagente)`, nunca abaixo
de 1; `max_subagentes` fixa o valor. RAM disponível vem de `/proc/meminfo` (`MemAvailable`); no
macOS, metade da física; desconhecida, vale o teto. O `SessionStart` responde
`additionalContext` com o número, o motivo (teto do perfil, memória, ou fixo) e a orientação de
agrupar tarefas pequenas. É contexto, não trava: um hook não decide quantos filhos o modelo abre.

## 9. Piso por repositório

`cakto-downshift.json`, procurado da raiz do projeto para cima, até 8 níveis, sem seguir symlink,
até 64 KB:

```json
{"versao": 1, "minimo": "haiku", "minimo_por_classe": {"complexa": "opus"},
 "minimo_por_risco": {"dinheiro": "opus", "segredo": "opus", "destrutivo": "opus", "dado_pessoal": "sonnet"}}
```

Só sobe. Arquivo inválido é ignorado e o `doctor` avisa onde. Dois templates em `docs/pisos/`:
`pagamentos.json` (dinheiro, segredo, cripto, destrutivo em opus) para `cakto-backend` e
`cakto-split`; `front.json` (segredo e destrutivo em opus; dinheiro, dado pessoal e acesso no mínimo
sonnet) para `cakto-frontend`, `cakto-checkout`, `cakto-checkout-v2`, `split-admin` e upsell. O
checkout é front: quase todo componente cita pix ou cartão, e com dinheiro em opus nada sairia dali.
Cada template tem um teste que o carrega.

## 10. Guardas

Valem em qualquer perfil, nesta ordem:

1. **agente nomeado** (`subagent_type` fora de vazio e `general-purpose`) sem `model` na chamada:
   não escreve. `CAKTO_DOWNSHIFT_ROTEAR_NOMEADOS=1` desliga a guarda;
2. **modelo atual desconhecido:** não escreve;
3. **complexa ou com risco:** nunca rebaixa;
4. **sem confiança:** não rebaixa, exceto o degrau único do perfil `high`;
5. **só escreve família da lista da sessão** (`haiku`, `sonnet`, `opus` por padrão; `fable` entra
   só se listado em `perfil.json` → `modelos`), e nunca escreve o modelo que já está em vigor.

Subir tier (piso de repo ou de risco acima do modelo atual) é permitido e também passa pela regra 5.

**Toda decisão carrega motivos** em códigos fechados, sem texto do prompt: `CLASSE_CONFIANTE`,
`CLASSE_SEM_CONFIANCA`, `SEM_SINAL`, `RISCO_<categoria>`, `PISO_RISCO`, `PISO_REPO`,
`PISO_PERFIL`, `PERFIL_HIGH`, `GUARDA_AGENTE_NOMEADO`, `GUARDA_MODELO_DESCONHECIDO`,
`GUARDA_COMPLEXA`, `GUARDA_RISCO`, `GUARDA_SEM_CONFIANCA`, `GUARDA_FORA_DA_LISTA`, `FORA_DO_ESCOPO`.

## 11. Telemetria e custo

`eventos.jsonl`, uma linha por evento, `0600`, sem prompt, sem `cwd` completo (só o nome da pasta
do projeto), `session_id` como SHA-256 truncado. Quatro tipos:

- `decisao`: `tool_use_id`, nome do agente, classe, confiança, risco, perfil, piso aplicado, tier
  escolhido, modelo atual, modelo escrito ou `null`, motivos, `ms`;
- `resultado` (`PostToolUse` e `PostToolUseFailure` em `Task|Agent`): `tool_use_id`, modelo que o
  Claude Code reportou (`tool_response`), como o filho terminou (`concluido`, `erro`,
  `interrompido`, `desconhecido`). É a prova de que a reescrita foi aplicada;
- `uso` (`SubagentStop`): `agent_id`, tokens de entrada, saída, cache de leitura e de escrita,
  somados do transcript do filho; custo pelo catálogo;
- `falha`: hook e código do erro.

**Ligação custo ↔ decisão.** O `SubagentStop` não traz `tool_use_id`. A ligação é por sessão e
ordem: o `uso` casa com a `decisao` mais recente da mesma sessão ainda sem uso, dentro de 2 horas.
Com filhos em paralelo as pontas podem trocar; o evento guarda `ligacao: "ordem"` e o `stats` conta
quantas foram assim. Sem ligação, sem economia.

**`stats --dias 7|30`:** decisões por classe e tier; reescritas aplicadas (com `resultado` que
confirma) e seguradas, por motivo; custo real por tier e por sessão; e a economia estimada como
`custo real − custo dos mesmos tokens no modelo que o filho teria herdado`, sempre com a etiqueta
"estimado pelo catálogo, não é fatura" e `sem dado` quando não há ligação. Nenhum número é
inventado para preencher tabela.

**Catálogo** (`catalogo.py`): id, família, tier e preço por milhão (entrada, saída, cache) de Haiku
5.5, Sonnet 5.5, Opus 5.5 e Fable 5.1, com a data da tabela. Atualizar preço é PR.

## 12. CLI e instalação

```
cakto-downshift try "<texto>" [--modelo-atual opus] [--agente backend]   o que o hook faria, com os motivos
cakto-downshift economia [low|medium|high] [subagentes N|auto] [gb N]
cakto-downshift stats [--dias 7]
cakto-downshift doctor          versão, pasta de estado, escopo, perfil, hooks encontrados, piso do cwd
cakto-downshift instalar [--escopo <pasta>] [--aplicar]
cakto-downshift desinstalar [--aplicar]
cakto-downshift hook pre-tool-use | session-start | subagent-stop | post-tool-use
```

**Bootstrap:**
```
python3 -m venv ~/.cakto-downshift/venv
~/.cakto-downshift/venv/bin/pip install git+https://github.com/MatheusAltrao/cakto-downshift
~/.cakto-downshift/venv/bin/cakto-downshift instalar --escopo ~/Documentos/codigos/trabalho/cakto --aplicar
```

`instalar` sem `--aplicar` mostra o plano. Com `--aplicar`: grava `escopo`, cria `perfil.json` em
`medium` se não existir, e escreve os quatro hooks no `~/.claude/settings.json` com `json` do
Python: backup datado, preserva tudo o que não é nosso, remove hooks nossos antigos antes de pôr os
novos, escreve através de symlink e mantém o modo do arquivo. O comando dos hooks é
`"~/.cakto-downshift/venv/bin/cakto-downshift" hook <nome>`, com o caminho entre aspas. Os hooks
valem na próxima sessão. `desinstalar` tira os hooks e deixa o estado.

**Atualizar:** `pip install --upgrade git+...` no mesmo venv. O `doctor` mostra a versão instalada
(do `pyproject`) e o commit, quando instalado de git.

## 13. Testes

pytest, no CI do GitHub a cada push:

- **golden set** em `tests/golden/`: JSONL com `texto`, `classe`, `confianca`, `risco`, PT-BR e EN,
  prompts sintéticos no formato das tarefas da Cakto, nenhum dado de cliente;
- **invariantes** (propriedades sobre o golden set e sobre prompts gerados): risco nunca vai para
  haiku; complexa nunca é rebaixada; `low` nunca escreve haiku; `high` nunca escreve haiku sem
  confiança nem rebaixa risco; agente nomeado nunca é escrito por padrão; modelo desconhecido nunca
  é escrito; entrada inválida responde `{}` com exit 0;
- **hook ponta a ponta** por subprocess, com payloads reais dos quatro eventos do Claude Code,
  conferindo o JSON de saída e a linha gravada;
- **latência:** 200 spawns abaixo de 150 ms cada; prompt de 1 MB abaixo de 500 ms;
- **instalador** contra um `settings.json` de exemplo com hooks alheios, symlink, rodada repetida e
  arquivo ausente;
- **templates de piso** carregam e aplicam o que prometem.

## 14. Decisões registradas

- Python e stdlib: o time mantém Python; um subagente é um processo novo por spawn, e import pesado
  sairia do orçamento.
- `{}` no no-op em vez de `allow`: aprovar o spawn era efeito colateral, não intenção.
- Orçamento de subagentes como contexto, não trava: o hook vê um spawn por vez; quem decide abrir
  seis é o modelo, antes de qualquer hook rodar.
- Agente nomeado preservado por padrão: tira todo nomeado do roteador, inclusive os que herdam Opus.
  O ganho nesses vem de `model:` no frontmatter, documentado em `docs/agentes.md`.
- Vocabulário de risco em Python com teste ao lado, não em YAML: foi em lista sem teste que os
  falsos positivos nasceram.
- Nome: cakto-downshift. "Downshift" é também o nome do projeto do Tiago; ferramenta privada,
  risco de marca praticamente nulo, decisão do dono.

## 15. Pendências para depois da v1

Medir uma semana antes de afirmar economia; golden set com prompts reais anonimizados do time; se o
time adotar, distribuição pelo `/sincronizar` do brain e tabela de `model:` dos agentes no brain;
BCP do card do Plane como sinal, com cache local.
