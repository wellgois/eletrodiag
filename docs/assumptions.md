# Premissas e limites

Tudo o que os dados de demonstração mostram depende das premissas abaixo. **As sessões de estudantes são sintéticas.** Os números servem para exercitar o pipeline e para planejar um piloto real, não para provar que o método funciona.

## O que é medido e o que é assumido

| Item | Origem | Confiança |
|---|---|---|
| Tensões e correntes de cada defeito | Simulação DC (MNA + Newton-Raphson) com 150 amostras Monte Carlo por defeito | Boa para circuitos simples de DC. Não modela AC, temperatura nem ruído |
| Modelos de componentes | Resistor ideal, LED e diodo por Shockley, zener por exponencial reversa, BJT Ebers-Moll NPN, MOSFET canal N (lei quadrática com diodo de corpo), regulador linear 78xx (comportamental), fusível e enrolamento como resistências pequenas, capacitor como circuito aberto | Simplificados. Valores de catálogo, não de folha de dados |
| Blocos do inversor | Cinco circuitos de topologia típica (entrada, fontes auxiliares, primário push-pull, barramento de alta tensão, ponte H), todos em CC de um semiciclo | **Topologia de referência, não o esquema do aparelho de teste.** Trocar pelos valores medidos na placa real (ver [inverter_blocks.md](inverter_blocks.md)) |
| Probabilidade a priori de cada defeito | Pesos escolhidos por mim (`PRIOR_W`) | Palpite informado. Deve ser substituída por estatística de bancada |
| Tempo por passo | Medianas assumidas: tensão 35 s, corrente 80 s, teste de componente 110 s | **Premissa sem medição.** É o que mais pesa no ganho de tempo |
| Erro de leitura grosseiro | 6% (iniciante) a 3% das leituras | Premissa |
| Método atual do estudante | Acha o componente defeituoso com probabilidade 0,85 a 0,92 quando o testa; falso positivo de 0,06 a 0,03 | Premissa. Se for perfeito, o app perde em taxa de sucesso (ver abaixo) |
| Desistência | Probabilidade fixa por passo a partir do 3º | Premissa |

Os valores exatos estão no código de `src/eletrodiag/synth/students.py` (constantes no topo) e podem ser mudados.

## Sobre a simulação

- Fonte com resistência interna de 1 Ω, para modelar o limite de corrente de uma fonte real.
- O multímetro carrega o nó medido com 10 MΩ. Isso importa em nós de alta impedância.
- Pinos desconectados por falha recebem 1 GΩ para o terra, para o solucionador convergir.
- Convergência: 1 V de limite de passo, fallback por source stepping, GMIN de 1e-12.
- Tolerâncias do Monte Carlo: resistores ±5%, fontes ±2%, `Is` e `beta` log-normais, zener ±5%.
- Modelo de defeitos: um defeito por vez. **Defeito duplo não é considerado**, e na bancada ele acontece (um transistor em curto costuma levar um resistor junto).

## Sobre o diagnóstico

- Posterior bayesiano com verossimilhança gaussiana, sigma = √(desvio do Monte Carlo² + incerteza do multímetro²).
- Mistura com densidade uniforme (`outlier_eps` = 0,03) para tolerar leitura errada sem derrubar a hipótese correta.
- Próxima medição: a que mais separa pares de hipóteses de componentes diferentes, por unidade de custo (tensão = 1, corrente = 2,5).
- Parada: 80% de confiança e pelo menos 2 medições.
- Separabilidade: soma das distâncias de Bhattacharyya sobre todos os observáveis; limiar 3,0. Classes: `distinguivel_por_tensao`, `requer_corrente`, `indistinguivel_eletricamente`, `mesmo_componente`.

## Resultados de demonstração e sua robustez

Resumo de [sensitivity.md](sensitivity.md) (base, 10 circuitos):

- Tempo médio até a decisão cai de ~8,5 min (método atual) para ~2,7 min (guiado). Esse ganho vem principalmente da premissa de que testar componente custa mais do que medir tensão.
- Passos caem de 4,28 para 3,36 (média dos 10 circuitos).
- Taxa de sucesso: 84% contra 81%. **Se o método atual for perfeito, o app fica abaixo: 83% contra 99%.** A queda é maior nos blocos do inversor, onde muitas falhas são eletricamente indistinguíveis com o circuito energizado (ponte H e primário push-pull).
- Guiado versus medição em ordem aleatória: a diferença é pequena (3,36 contra 3,76 passos).

## Limites conhecidos

1. **Dados de estudantes são sintéticos.** Nenhuma conclusão sobre aprendizado ou usabilidade é suportada.
2. **Dez circuitos, o maior com 15 componentes.** O comportamento em placas reais completas (dezenas de componentes, CIs de controle, malhas de realimentação, chaveamento) não foi testado. Os blocos do inversor são instantâneos de um semiciclo em CC: não representam SPWM, tempo morto, transformador acoplado nem filtro LC.
3. **Só tensão e corrente.** Teste de diodo e de resistência com a placa desligada (o melhor teste para MOSFET em curto e fusível aberto) ainda não são observáveis do app.
4. **O estudante precisa saber medir.** O app não ensina a usar o multímetro. O treinamento embutido mostra onde pôr as ponteiras no esquema.
5. **Teto físico.** Alguns pares de defeitos só se separam testando o componente fora do circuito. O app avisa, mas a decisão final cabe ao estudante.
6. **Sem validação elétrica externa.** O simulador foi comparado a casos analíticos (divisor, LED, BJT, zener, chave MOSFET, regulador) nos testes, não a um simulador de referência como o SPICE. Comparar com ngspice é um passo recomendado.
7. **Visual conferido só em Chromium sem interface.** Os esquemas do inversor foram vistos em captura de tela; falta conferir em celular e outros navegadores.
8. **Ferramentas de BI externas não testadas.** As conexões descritas em [bi_guide.md](bi_guide.md) seguem a documentação de cada ferramenta, mas não foram executadas aqui.
