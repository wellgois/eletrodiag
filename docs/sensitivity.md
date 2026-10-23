# Análise de sensibilidade

Dados **sintéticos**. Cada linha refaz a simulação com premissas diferentes (120 cenários por circuito, 10 circuitos, 3 métodos, mesma semente). "Δ" é guiado menos método atual.

| Premissa | Sucesso guiado | Sucesso atual | Δ sucesso | Passos guiado | Passos atual | Δ passos | Min guiado | Min atual |
|---|---|---|---|---|---|---|---|---|
| Base (premissas do pipeline) | 84% | 80% | +4,8 p.p. | 3,37 | 4,24 | -0,86 | 2,7 | 8,5 |
| Método atual perfeito (acha o defeito sempre, sem falso positivo) | 83% | 99% | -15,8 p.p. | 3,44 | 4,15 | -0,72 | 2,8 | 8,3 |
| Teste de componente rápido (45 s em vez de 110 s) | 84% | 80% | +4,8 p.p. | 3,37 | 4,24 | -0,86 | 2,7 | 3,5 |
| Erros de leitura dobrados (ponteira invertida, escala, ponto errado) | 85% | 79% | +5,5 p.p. | 3,41 | 4,22 | -0,80 | 2,7 | 8,4 |
| Pior caso para o app (os três acima juntos) | 82% | 98% | -16,1 p.p. | 3,38 | 4,05 | -0,67 | 2,7 | 3,2 |

## Leitura

- Os circuitos básicos têm de 3 a 6 componentes: o método atual já acaba em poucos testes e o ganho em **passos** é pequeno. Nos blocos do inversor (até 15 componentes) o método atual precisa de mais testes e o ganho em passos e em tempo é maior, mas a taxa de sucesso do app cai nos blocos em que muitas falhas não se separam com o circuito energizado (primário e ponte H): ali o teste de componente com a placa desligada faz falta.
- O ganho em **tempo** vem sobretudo da premissa de que testar um componente (desligar, levantar um terminal, medir) custa bem mais que uma medição de tensão no circuito ligado. Se essa premissa estiver errada, o ganho encolhe.
- O ganho em **sucesso** depende da taxa de acerto assumida para o método atual. Se o método atual acerta sempre, o app fica ABAIXO em sucesso: ele tem um teto, porque alguns pares de defeitos não se separam só com o multímetro (ver `v_ambiguidade`). Nesse caso o app só compensa se os passos e o tempo caírem de verdade.
- A simulação do app para na decisão e não modela o teste de confirmação que ele recomenda. Um estudante que confirma antes de trocar recupera parte desse teto.
- Estes números orientam o desenho do piloto real. Eles não substituem medir estudantes de verdade.
