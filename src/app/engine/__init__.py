"""Motor de decisão do Koru v2.

Código puro: sem I/O, sem LLM, sem conhecimento de HTTP ou banco. É aqui que o sistema
decide (P1), e é por isso que uma sessão pode ser recomputada a partir das evidências
persistidas, sem chamar modelo nenhum (P5).
"""
