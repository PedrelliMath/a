def init_custom_open_api(app):
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        
        from fastapi.openapi.utils import get_openapi
        from app.config import settings
        
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )
        
        # Garanta que components existe
        if "components" not in openapi_schema:
            openapi_schema["components"] = {}
        
        # Defina o OAuth2 Security Scheme
        openapi_schema["components"]["securitySchemes"] = {
            "OAuth2": {  # ← Nome do scheme
                "type": "oauth2",
                "flows": {
                    "authorizationCode": {
                        "authorizationUrl": f"{settings.auth.issuer}/protocol/openid-connect/auth?client_id=chatbot-frontend",
                        "tokenUrl": f"{settings.auth.issuer}/protocol/openid-connect/token",
                        "scopes": {
                            "openid": "OpenID Connect",
                            "profile": "User profile",
                            "email": "User email"
                        }
                    }
                }
            }
        }
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    return custom_openapi