"""Ambiente mínimo para importar `app`.

`app.config` instancia `Settings()` em tempo de import (`config.py:133`), então importar
qualquer módulo do projeto exige a configuração inteira presente — inclusive credenciais.
Isso torna o código não-importável fora de um ambiente completo, e é o que este arquivo
contorna. A correção de verdade (settings preguiçoso / injetado) está na Onda 3 do
`docs/ROADMAP.md`.

Nota: `helicone_api_key` e `openai_api_key` são declarados com `default=None` mas tipados
como `SecretStr`, que não aceita `None`. O default nunca funciona e as duas variáveis são,
na prática, obrigatórias.
"""

import os

VARIAVEIS_DE_TESTE = {
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_DB": "test",
    "POSTGRES_USER": "test",
    "JWKS_URI": "realms/test/protocol/openid-connect/certs",
    "ISSUER": "realms/test",
    "JWT_AUDIENCE": "test",
    "KEYCLOAK_SERVER_URL": "localhost:8080",
    "HELICONE_API_KEY": "test",
    "HELICONE_ENABLED": "false",
    "OPENAI_API_KEY": "test",
}

for chave, valor in VARIAVEIS_DE_TESTE.items():
    os.environ.setdefault(chave, valor)
