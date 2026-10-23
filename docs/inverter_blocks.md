# Blocos de inversor

Cinco circuitos do simulador representam as partes de um inversor CC-CA senoidal de alta frequência, para os primeiros testes de bancada (inversor SOECOPO 15000W, que na prática é um inversor de 1,2 kW contínuos). Os valores seguem uma **topologia típica de referência**; o esquema real do aparelho ainda não foi levantado e não existe publicado (ver [assumptions.md](assumptions.md)). Troque os números pelos medidos na placa real antes de confiar nas tensões esperadas.

## O que é e o que não é

- São **instantâneos em corrente contínua** de um semiciclo: M1 e Q1/Q4 conduzem, M2 e Q2/Q3 estão cortados. Servem para saber a polarização de cada bloco, não o chaveamento.
- O simulador não representa SPWM, tempo morto, acoplamento do transformador, filtro LC nem a malha de controle.
- A bateria é de 24 V. Modelos de 12 V têm fontes auxiliares diferentes (o 7815 não regula com 12 V na entrada).

## Os cinco blocos

| Circuito | O que mostra | Componentes | Medições | Falhas |
|---|---|---|---|---|
| `inv_entrada` | Bateria, quatro fusíveis em paralelo, MOSFET de proteção de polaridade, carga | 10 | 6 | 30 |
| `inv_fontes_aux` | 7815 (+15 V) e 7805 (+5 V) em cascata, diodo de entrada | 6 | 6 | 18 |
| `inv_primario` | Push-pull: fusível, derivação central, dois enrolamentos, dois MOSFETs e resistores de porta | 12 | 8 | 42 |
| `inv_barramento_hv` | Retificador, capacitor do barramento (~360 V CC), divisor de realimentação | 6 | 5 | 18 |
| `inv_ponte_h` | Ponte H com quatro MOSFETs, shunt, acionadores | 15 | 7 | 66 |

Os dois últimos têm aviso de **alta tensão** no app. Os outros três têm aviso de corrente alta ou de alimentação pela bateria.

## Modelos novos

| Elemento | Modelo | Parâmetros típicos |
|---|---|---|
| MOSFET canal N | Lei quadrática (triodo e saturação) com sublimiar suave e diodo de corpo | Baixa tensão: Kp 144 A/V², Vth 3 V (~1 mΩ, vários em paralelo). Alta tensão: Kp 0,35 A/V², Vth 3,5 V (~0,25 Ω) |
| Regulador 78xx | Comportamental: saída = mínimo de Vset e (entrada − 2 V), resistência de saída 0,2 Ω, corrente quiescente 4 mA; sem entrada, sem corrente | 15 V e 5 V |
| Fusível e enrolamento | Resistência pequena | 0,4 a 1,5 mΩ e 20 mΩ |
| Capacitor | Circuito aberto em CC (R = 10 GΩ); só as falhas de curto e fuga aparecem | |

## Falhas modeladas

MOSFET: dreno, fonte ou porta aberta, curto dreno-fonte, porta-fonte ou dreno-porta, e Rds alto. Fusível: aberto ou resistivo. Enrolamento: aberto. Capacitor: curto ou fuga. Regulador: sem saída, entrada em curto com a saída, saída baixa. Diodo: aberto ou curto. O peso a priori de MOSFET em curto dreno-fonte é 3 (aberto 1), por ser a falha mais relatada em reparos; é um palpite informado e deve ser medido.

## O que a simulação já mostra

- Um fusível aberto quase não muda a tensão (milivolts); aparece pela corrente dos fusíveis vizinhos ou pelo teste de continuidade com a placa desligada.
- MOSFET de proteção de polaridade aberto deixa a carga sem terra: a tensão do terra da carga sobe ao nível da bateria.
- Curto de perna na ponte H (Q2 ou Q3 em curto com o oposto ligado) derruba o barramento e a corrente de carga some.
- Nos blocos do primário e da ponte H, centenas de pares de defeitos não se separam só com medição energizada. O complemento é o teste de diodo e de resistência com a placa desligada, que ainda não é um tipo de medição do app.

## Segurança

A bateria de um inversor desse porte entrega centenas de ampères. O barramento de alta tensão guarda carga mesmo desligado. Procedimento: bateria desconectada, capacitores descarregados e conferidos com o multímetro, e só então medição de resistência e diodo. Medição energizada somente com fonte limitada em corrente e ponta de prova adequada, com acompanhamento de pessoa experiente.
