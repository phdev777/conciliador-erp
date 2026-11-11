# Conciliador ERP

Lê os **Processos de Compra** do Minerion SGA (somente consulta) e **acrescenta** as OCs novas na aba
`Base_Compras` da planilha de metas (a planilha nunca é substituída). Dois jeitos de usar:

| | Método A — com Claude | Método B — automático |
|---|---|---|
| Como roda | No Claude Code: `/conciliar` | Duplo clique em `CONCILIAR.bat` |
| Leitura da tela | OCR do Windows **+ revisão visual do Claude** | Só OCR do Windows (com tripla conferência de valores) |
| Precisa | Claude Code | Nada (usa `programa\Conciliador.exe`) |

## Organização da pasta
```
CONCILIAR.bat        <- método automático (duplo clique)
README.md            <- este guia
programa\            <- Conciliador.exe (não precisa de Python)
sistema\             <- código-fonte, config padrão, INSTALAR.bat e GERAR_EXE.bat (manutenção)
skills\conciliar\    <- skill /conciliar do Claude (método com Claude)
.claude-plugin\      <- manifesto do plugin/marketplace
```
| Melhor para | Precisão máxima, nomes de itens/fornecedores limpos | Rodar sozinho, rápido, sem custo |

## Antes de começar (os dois métodos)
1. **Minerion SGA** aberto **só na empresa** que vai conciliar (uma empresa por vez).
2. **Planilha da empresa aberta no Excel**, do jeito que você sempre abre (pelo OneDrive/SharePoint, com salvamento automático).
3. Durante a leitura do ERP (~25 s por OC) **não mexa no mouse/teclado**.

## Instalação
- **Método B (sem Claude)**: baixe o repositório (botão *Code → Download ZIP*), extraia e dê duplo clique em `CONCILIAR.bat`.
  Não precisa instalar nada. (Quem preferir Python 3.10+: `sistema\INSTALAR.bat`.)
- **Método A (com Claude)** — uma vez, num terminal (o GitHub pede login na primeira vez, se o repositório for privado):
  ```
  claude plugin marketplace add phdev777/conciliador-erp
  claude plugin install conciliador-erp@conciliador-erp
  ```
  (ou, no Claude Code, `/plugin` → adicionar marketplace → `phdev777/conciliador-erp`). Abra uma **sessão nova** e digite `/conciliar`.
  Atualizar depois: `claude plugin marketplace update conciliador-erp` e `claude plugin update conciliador-erp@conciliador-erp`.
- **Manutenção**: depois de alterar o código, rode `sistema\GERAR_EXE.bat` para atualizar `programa\Conciliador.exe`
  e aumente a versão em `.claude-plugin\plugin.json`.
- Requisito do Windows: idioma **Português (Brasil)** instalado (já vem nos PCs em pt-BR) — o OCR é o nativo do Windows.

## Configuração (`Documentos\ConciliadorERP\config.json`)
Criada na primeira execução. Uma entrada por empresa:
```json
"empresa1": { "titulo_erp": "NOME DA EMPRESA", "planilha": "base_empresa1.xlsx", "aba": "Base_Compras",
            "solicitante": "Nome do Solicitante", "texto_a_vista": "A VISTA", "texto_prazo": "{n} dias" }
```
- `titulo_erp`: trecho que aparece no título do Minerion quando a empresa está aberta.
- `planilha`: **nome** do arquivo aberto no Excel (não precisa do caminho).
- Para outra empresa, copie um bloco e ajuste.

## O que é preenchido
| Coluna | Origem |
|---|---|
| Data Pedido | campo *Pedido* do processo |
| Nº RC | título da Análise Comparativa ("Requisição de Compra N"; sem requisição = 0) |
| Nº OC | número do processo |
| Forma de Pagamento | *Condições de Pagamento* da cotação vencedora (prazo 0 = à vista) |
| Tipo | Produtos/Serviços |
| OC (R$) | TOTAL da cotação vencedora, conferido com a soma dos itens e quantidade × unitário |
| Solicitante | fixo por empresa (config) |
| Linha do Pacote | **histórico da própria planilha** (fornecedor/item); se ambíguo, melhor sugestão + anotação |
| Item / Fornecedor | resumo dos itens / nome já usado no histórico |
| Fórmulas (Mês/Ano, SLA, Pacote) | copiadas da linha de cima |

Ficam **em branco**: Data Entrega, Saving, Localidade, Urgente, Registrado.
Tudo que precisa de conferência recebe uma **anotação na célula** começando com `Conciliador ERP:`.
Possíveis savings (subtotal × compra e cotações concorrentes) aparecem na anotação e no relatório.

## Segurança
- No ERP só são usadas as teclas: menu, F5, setas, Enter (na lista), F9 e Esc. Nunca Grava/Aprova/Reprova/Exclui.
- Se aparecer uma janela inesperada, a coleta para e guarda o progresso (rode de novo com `--execucao <pasta>`).
- OCs já existentes na planilha (pelo Nº OC) são puladas; nenhuma linha preenchida é alterada.

## Linha de comando
```
python -m conciliador diagnostico
python -m conciliador coletar --empresa empresa1 --de 01/11/2026 --ate 11/11/2026
python -m conciliador extrair --empresa empresa1
python -m conciliador lancar  --empresa empresa1 --simular   (mostra sem gravar)
python -m conciliador lancar  --empresa empresa1
python -m conciliador tudo    --empresa empresa1              (coletar + extrair + lancar)
```
Resultados: `Documentos\ConciliadorERP\<empresa>\<data_hora>\` → `relatorio.txt`, `extracao.json`, `capturas\`.

## Limitações conhecidas
- Depende do layout atual das telas do Minerion. Se o ERP mudar de layout/escala, os recortes precisam de ajuste (`conciliador\extrator.py`).
- No Método B, nomes de itens/fornecedores sem histórico podem ter pequenos erros de OCR (ex.: "CONSTRUCUO").
- A próxima evolução recomendada é ler direto do banco do Minerion (SQL Server, usuário só leitura) — elimina tela e OCR.
