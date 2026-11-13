# CPPP parameter sensitivity

## Quorum: exact binomial promotion probability (N = 5 agents)

Each cell is the probability that at least K validation votes are cast
when each honest agent validates with probability p and each compromised
agent votes yes with probability 1.

| compromised agents | K | p=0.2 | p=0.4 | p=0.6 | p=0.8 |
|---:|---:|---:|---:|---:|---:|
| 0 | 2 | 0.263 | 0.663 | 0.913 | 0.993 |
| 0 | 3 | 0.058 | 0.317 | 0.683 | 0.942 |
| 0 | 4 | 0.007 | 0.087 | 0.337 | 0.737 |
| 1 | 2 | 0.590 | 0.870 | 0.974 | 0.998 |
| 1 | 3 | 0.181 | 0.525 | 0.821 | 0.973 |
| 1 | 4 | 0.027 | 0.179 | 0.475 | 0.819 |
| 2 | 2 | 1.000 | 1.000 | 1.000 | 1.000 |
| 2 | 3 | 0.488 | 0.784 | 0.936 | 0.992 |
| 2 | 4 | 0.104 | 0.352 | 0.648 | 0.896 |

## Trust decay: exact rational iteration

| rho | alpha | half-life (ticks) | fixed point | 1% settling (ticks) | retire 0.75->0.50 (ticks) |
|---:|---:|---:|---:|---:|---:|
| 0.50 | 0.10 | 1 | 0.182 | 4 | 1 |
| 0.50 | 0.25 | 1 | 0.400 | 4 | 1 |
| 0.50 | 0.50 | 1 | 0.667 | 4 | 1 |
| 0.50 | 1.00 | 1 | 1.000 | 1 | 1 |
| 0.75 | 0.10 | 3 | 0.308 | 9 | 2 |
| 0.75 | 0.25 | 3 | 0.571 | 8 | 2 |
| 0.75 | 0.50 | 3 | 0.800 | 5 | 2 |
| 0.75 | 1.00 | 3 | 1.000 | 1 | 2 |
| 0.90 | 0.10 | 7 | 0.526 | 19 | 4 |
| 0.90 | 0.25 | 7 | 0.769 | 12 | 4 |
| 0.90 | 0.50 | 7 | 0.909 | 6 | 4 |
| 0.90 | 1.00 | 7 | 1.000 | 1 | 4 |
| 0.95 | 0.10 | 14 | 0.690 | 28 | 8 |
| 0.95 | 0.25 | 14 | 0.870 | 14 | 8 |
| 0.95 | 0.50 | 14 | 0.952 | 7 | 8 |
| 0.95 | 1.00 | 14 | 1.000 | 1 | 8 |
