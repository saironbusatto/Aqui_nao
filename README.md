# Comparação de Futebol x Jogadores

Sistema para comparar carreiras de jogadores de futebol, incluindo gols, lesões, tempo de jogo e projeções.

## Funcionalidades

- **Comparação entre Jogadores**: Gols na mesma idade, por time, na Copa do Mundo
- **Projeção de Gols**: Média por temporada, projeção para 30/35/40 anos
- **Histórico de Lesões**: Total de lesões, dias parados, jogos perdidos
- **Tempo de Jogo**: Minutos jogados vs banco, titularias
- **Interface Web**: Bootstrap 5, português, gráficos matplotlib

## Instalação

```bash
cd "/mnt/comparacao futebol x jogadores"
pip install -r requirements.txt
```

## Uso

```bash
cd src
python3 -m flask --app app run
```

Acesse http://localhost:5000

## Fontes de Dados

| Dado | Fonte |
|------|-------|
| Stats da carreira | FBref (via soccerdata) |
| Histórico de lesões | Transfermarkt |
| Copa do Mundo | Football-Data.org |

## Testes

```bash
python3 -m pytest tests/ -v
python3 -m pytest tests/ --cov=src --cov-report=term-missing
```

## Estrutura

```
src/
├── app.py                    # Flask web server
├── collectors/               # Coletoras de dados
│   ├── fbref_collector.py
│   ├── transfermarkt_collector.py
│   └── footballdata_collector.py
├── models/                   # Modelos de dados
│   ├── player.py
│   └── comparison.py
├── services/                 # Lógica de negócio
│   ├── comparison_engine.py
│   ├── projection.py
│   └── report.py
├── utils/                    # Utilitários
│   ├── cache.py
│   └── helpers.py
└── templates/                # Interface web
    ├── index.html
    └── compare.html
```
