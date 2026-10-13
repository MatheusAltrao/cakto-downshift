# Modelo sugerido por agente

O hook do cakto-downshift **não toca agente nomeado** (`subagent_type` diferente de vazio e de
`general-purpose`) quando a chamada não traz `model`. Sem `model:` no frontmatter, o agente nomeado
herda o modelo da sessão (Opus) e o roteador o deixa como está. Portanto **a economia nos agentes
nomeados vem desta tabela, não do hook**: o `model:` do frontmatter de cada agente é a decisão.

| Agente | `model:` sugerido | Por quê |
|---|---|---|
| `seguranca` | opus | auditoria de AppSec: o custo de errar é maior que o do token |
| `backend` | opus | regra de negócio de pagamentos, causa raiz entre camadas |
| `revisor-frontend` | opus | review com julgamento; falso negativo vira bug em produção |
| `design-frontend` | sonnet | UI e componentes: Sonnet dá conta |
| `teste-frontend` | sonnet | escrever e rodar testes |
| `teste-backend` | sonnet | escrever e rodar testes |
| `browser` | sonnet | automação e coleta de evidência, sem decisão de arquitetura |
| `Explore` | (não mexer) | agente embutido do Claude Code; segue como está |

Exemplo de frontmatter:

```markdown
---
name: teste-frontend
description: ...
model: sonnet
---
```

Se uma chamada traz `model` explícito, o roteador a trata como qualquer spawn e aplica guardas, piso
e perfil.
