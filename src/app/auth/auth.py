from typing import Dict
import os
import requests
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import jwt, JWTError
from app.config import settings
from app.logger import get_log

from app.models.current_user import CurrentUser

logger = get_log(__name__)
jwks = requests.get(settings.auth.jwks_uri).json()

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{settings.auth.issuer}/protocol/openid-connect/auth",
    tokenUrl=f"{settings.auth.issuer}/protocol/openid-connect/token",
    scopes={
        "openid": "OpenID Connect",
        "profile": "Profile information",
        "email": "Email address"
    },
    scheme_name="OAuth2"
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
    token: str = Security(oauth2_scheme)
) -> CurrentUser:
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