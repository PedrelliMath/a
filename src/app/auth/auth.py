from typing import Dict, Optional
import os
import requests
from fastapi import HTTPException, Request, Security
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import jwt, JWTError
from app.config import settings
from app.logger import get_log

from app.models.current_user import CurrentUser

logger = get_log(__name__)

# Verifica se auth está desabilitada para desenvolvimento local
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "false").lower() == "true"

# Só carrega jwks se auth estiver habilitada
jwks = None
if not DISABLE_AUTH:
    try:
        jwks = requests.get(settings.auth.jwks_uri).json()
    except Exception as e:
        logger.warning(f"Não foi possível carregar JWKS: {e}. Autenticação pode não funcionar.")

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{settings.auth.issuer}/protocol/openid-connect/auth",
    tokenUrl=f"{settings.auth.issuer}/protocol/openid-connect/token",
    scopes={
        "openid": "OpenID Connect",
        "profile": "Profile information",
        "email": "Email address"
    },
    scheme_name="OAuth2",
    auto_error=not DISABLE_AUTH  # Não retorna erro 401 automaticamente se auth desabilitada
)

def get_public_key(token: str) -> Dict:
    try:
        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid")
        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if not key:
            raise Exception("Chave pública não encontrada")
        return key
    except Exception as e:
        logger.info(str(e))
        raise HTTPException(status_code=401, detail="Erro ao obter chave pública")

def get_current_user(
    request: Request,
    token: Optional[str] = Security(oauth2_scheme)
) -> CurrentUser:
    # Modo desenvolvimento sem autenticação
    if DISABLE_AUTH:
        logger.info("Autenticação desabilitada - usando usuário de desenvolvimento")
        fake_user = CurrentUser(
            id="dev-user-123",
            name="dev_user",
            scopes=["openid", "profile", "email"]
        )
        request.state.current_user = fake_user.model_dump()
        return fake_user
    
    # Modo produção com autenticação
    try:
        key = get_public_key(token)

        payload = jwt.decode(
            token,
            key=key,
            algorithms=[settings.auth.jwt_algorithm],
            audience="account",
            issuer=settings.auth.issuer,
        )

        token_scopes = payload.get("scope", "").split()
        if not any(scope in token_scopes for scope in settings.auth.jwt_scopes):
            raise HTTPException(status_code=403, detail="Escopo insuficiente")

        current_user = {
            "id": payload["sub"],
            "name": payload.get("preferred_username"),
            "scopes": token_scopes,
        }

        request.state.current_user = current_user
        return CurrentUser(**current_user)

    except JWTError as e:
        logger.info(str(e))
        raise HTTPException(status_code=401, detail="Token inválido")