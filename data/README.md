# Origem da base

- Fonte explicativa: https://jakevdp.github.io/blog/2018/09/13/waiting-time-paradox/
- CSV: https://gist.githubusercontent.com/jakevdp/82409002fcc5142a2add0168c274a869/raw/1bbabf78333306dbc45b9f33662500957b2b6dc3/arrival_times.csv
- Provedor original: Washington State Transportation Center; disponibilização por Jake VanderPlas.
- Revisão fixa do gist: `1bbabf78333306dbc45b9f33662500957b2b6dc3`.
- Download realizado em 24/09/2026.
- SHA-256: `549438cf42664a0e71c723173ed4ad5ab407884ca14a52aaa0eb0d404230453e`.
- 39.157 registros no CSV; 6.634 no recorte C/sul/431; 6.547 após tratamento.
- 83 registros inválidos, 4 linhas de correspondências ambíguas, nenhuma duplicata exata no recorte. Três ajustes de meia-noite.

A cópia não foi alterada. A base tratada, com seu próprio hash no modelo, está em `artifacts/v1/clean.csv`. A aplicação não precisa baixar este arquivo durante o uso. Não se atribui uma licença nova aos dados de terceiros.
