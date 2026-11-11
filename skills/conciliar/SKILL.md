---
name: conciliar
description: Concilia as compras do ERP Minerion SGA com a planilha de metas de suprimentos (aba Base_Compras) — lê os Processos de Compra do período (somente consulta), revisa visualmente o que o OCR leu e acrescenta as OCs novas na planilha aberta no Excel. Use quando pedirem para conciliar/lançar/preencher compras do Minerion na planilha (empresa definida no config).
---

# Conciliador ERP (método com Claude)

A raiz do plugin fica dois níveis acima deste arquivo. Chame de CMD o jeito de rodar a ferramenta:
- Se existir `<raiz>\programa\Conciliador.exe` → CMD = `& "<raiz>\programa\Conciliador.exe"` (não precisa de Python).
- Senão, com Python 3.10+: `cd "<raiz>\sistema"` e CMD = `python -m conciliador`
  (se faltar pacote: `python -m pip install --user -r requirements.txt`).
Nos passos abaixo, `python -m conciliador` significa CMD.

## Regras que não podem ser quebradas
- O ERP é **somente consulta**. Nunca gravar, aprovar, reprovar, excluir ou "Seleciona [Enter]" na Análise Comparativa. O comando `coletar` já usa só teclas seguras — não envie teclas por conta própria ao Minerion.
- A planilha é **preenchida, nunca substituída** (ela alimenta painéis). Só o comando `lancar` escreve, e só acrescenta linhas no fim, na planilha **aberta no Excel** pelo usuário.
- Não inventar dados. O que não der para confirmar fica com anotação `Conciliador ERP: ...` na célula.
- Colunas Data Entrega, Localidade, Urgente (S/N), Registrado (S/N) e Saving ficam em branco (regra do usuário), salvo instrução contrária.

## Passo a passo
1. **Conferir o ambiente**: `python -m conciliador diagnostico`. Confirme com o usuário a empresa (chave do `config.json`) e o período (padrão: dia 1 do mês até hoje). Peça que deixe o Minerion aberto **na empresa certa** e a planilha da empresa **aberta no Excel**.
2. **Coletar** (avise: "não mexa no mouse/teclado"); rode em segundo plano porque leva ~25 s por OC:
   `python -m conciliador coletar --empresa <emp> --de DD/MM/AAAA --ate DD/MM/AAAA`
   Se for interrompido, rode de novo com `--execucao <pasta>` (retoma sem repetir).
3. **Extrair + gerar lotes de revisão**: `python -m conciliador lotes --empresa <emp>` (roda o OCR e cria `revisao/lote_XX.png`).
4. **Revisar cada lote com a visão** (Read nas imagens). Cada bloco mostra a tela do processo, a Análise Comparativa (colunas de cotações; a vencedora tem preço **verde**) e, em azul, o que o OCR leu.
   Compare e corrija no `extracao.json` da execução **somente** campos errados:
   `rc` (título "Requisição de Compra N"; sem isso = 0), `pedido` (campo Pedido, DD/MM/AAAA), `tipo` ("Produto"/"Serviço"),
   `valor` (TOTAL da coluna vencedora = campo Compra), `pagamento` (Condições de Pagamento da vencedora, ex. "15 dias Direto"/"A VISTA"),
   `fornecedor_erp` (nome sem CNPJ), `itens` (nomes dos itens, sem código/NCM), `situacao` ("Ordem de Compra" ou outra).
   Ao corrigir um campo, remova de `problemas` o aviso correspondente; acrescente um aviso se algo for duvidoso.
5. **Simular**: `python -m conciliador lancar --empresa <emp> --simular` e mostre ao usuário o resumo (linhas, anotações).
6. **Lançar** só com o OK do usuário: `python -m conciliador lancar --empresa <emp>`.
7. **Relatar**: quantas OCs entraram (e em quais linhas), quais foram puladas por já existirem, quais não foram lançadas (C.Preco etc.) e as anotações para conferência. O texto fica em `relatorio.txt` na pasta da execução.

## Dúvidas comuns
- "Excel ocupado": o usuário está editando uma célula — peça para sair da edição; o comando tenta de novo sozinho.
- Linha do Pacote vem do histórico da própria planilha; quando ambígua, aplica a melhor sugestão e anota o motivo.
- Pasta das execuções: `Documentos\ConciliadorERP\<empresa>\<data_hora>\` (capturas, extracao.json, relatorio.txt).
