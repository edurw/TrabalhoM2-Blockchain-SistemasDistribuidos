# Enunciado do trabalho

Os objetivos deste trabalho são:

1. Implementar um sistema baseado em **comunicação** e **arquitetura peer-to-peer (P2P)**;
2. Compreender as principais funcionalidades de uma **blockchain**;
3. Analisar e resolver problemas de consistência de dados em redes **descentralizadas**;
4. Representar a arquitetura do sistema e do software desenvolvido;
5. Documentar e apresentar a solução de forma clara e estruturada.

## Requisitos Iniciais
1. Crie uma conta no ZeroTier.
2. Conecte dois computadores à mesma rede virtual privada.
3. Configure o ambiente para que ambos compartilhem a mesma aplicação de blockchain desenvolvida (isto é, execute o mesmo código nas duas máquinas).

## Cenário de teste

Com dois computadores conectados à rede, execute os seguintes passos:

### Primeiro passo

Realize as seguintes operações em sequência

1. **Computador 1**: minera 2 blocos em sequência
2. **Computador 1**: transfere 10 moedas para Computador 2

### Segundo passo

Realize as seguintes operações em paralelo (deve ser solicitado ao mesmo tempo, ou quase ao mesmo tempo, para ambos computadores)

1. **Computador 1**: minera 1 bloco
2. **Computador 2**: minera 1 bloco

### Terceiro passo

Verifique os estados da blockchain em cada computador.

1. **Computador 1**: verifique o estado da blockchain usando a função pronta apresentada
2. **Computador 2**: verifique o estado da blockchain usando a função pronta apresentada

## Verificação dos resultados:

O computador que finalizar a mineração primeiro deverá ver algo assim:
```
Index: 0, Hash: 0...,          Tx: 0
Index: 1, Hash: 000024f3c0..., Tx: 1
Index: 2, Hash: 000087593f..., Tx: 1
Index: 3, Hash: 0000b110ba..., Tx: 2
```

O computador que finalizar a mineração por último verá dois blocos com o mesmo índice (Index 3), mostrando uma inconsistência.
```
Index: 0, Hash: 0...,          Tx: 0
Index: 1, Hash: 000024f3c0..., Tx: 1
Index: 2, Hash: 000087593f..., Tx: 1
Index: 3, Hash: 0000b110ba..., Tx: 2
Index: 3, Hash: 0000f190c7..., Tx: 2
```

## Análise

Esses resultados nos mostram que houve uma inconsistência na blockchain pois os índeces deveriam ser sequênciais e únicos.

## Tarefa

Identifique a causa do erro e como é chamado esse tipo de problema. Em seguida, pesquise por soluções adotadas para este tipo de problema em moedas digitais, selecione um método e faça uma implementação para corrigir esse problema.

Monte um relatório contendo:

1. A verificação inicial com estado inconsistente pelos computadores 1 e 2 com prints dos resultados obtidos;
2. Apresente o raciocínio para a causa do erro;
3. Apresente os métodos mais utilizados para resolver tal problema;
4. Selecione um método e faça sua implementação para corrigir o erro e manter a consistência da blockchain;
5. Apresente os novos resultados;
6. Apresente a arquitetura de sistema e a arquitetura de software usando diagramas.

Ao final, torne público o seu código no github (opcionalmente, grave uma apresentação explicando as alterações realizadas). Adicione no relatório os links para o código e para a apresentação. Submeta o relatório em formato PDF.

## Critério de avaliação

1. Clareza na justificativa para causa do erro;
2. Relevância do método selecionado para correção do erro;
3. Efetividade da solução implementada;
4. Apresentação da arquitetura da solução; e
5. Qualidade do relatório, código e apresentação.


## Pontos extras:

Para aqueles que estiverem interessados em ganhar ponto extra, segue algumas outras sugestões de melhorias:

1. Possibilitar que 1 novo par descubra todos os pares atuais participantes da rede a partir de um único par (easy)
2. Possibilitar múltiplas conexões de clientes paralelas na thread do servidor (easy)
3. Garantir que alguém tentando fazer uma transação não esteja utilizando uma moeda já gasta (hard)

Caso você descubra outras vulnerabilidades e pontos de melhoria, apresente-ás. Você ganhará ponto extra por isso. 
