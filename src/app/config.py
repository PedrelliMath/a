from pydantic import BaseModel, SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class PostgresSettings(BaseModel):
    postgres_host: str
    postgres_port: int
    postgres_password: SecretStr
    postgres_db: str
    postgres_user: str = Field(default="postgres")
    
    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:"
            f"{self.postgres_password.get_secret_value()}@"
            f"{self.postgres_host}:{self.postgres_port}/"
            f"{self.postgres_db}"
        )


class ApplicationSettings(BaseModel):
    app_mode: str = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    
    @property
    def is_development(self) -> bool:
        return self.app_mode.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        return self.app_mode.lower() == "production"

class AuthenticationSettings(BaseModel):
    jwks_uri: str
    issuer: str
    jwt_algorithm: str = Field(default="RS256")
    jwt_audience: str
    jwt_scopes: list[str] = Field(default="openid")

class HeliconeSettings(BaseModel):
    """Configurações para observabilidade com Helicone"""
    helicone_api_key: SecretStr = Field(default=None)
    helicone_enabled: bool = Field(default=True)
    helicone_base_url: str = Field(default="https://oai.helicone.ai/v1")
    
    @property
    def is_configured(self) -> bool:
        """Verifica se o Helicone está configurado corretamente"""
        return self.helicone_enabled and self.helicone_api_key is not None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    postgres_host: str
    postgres_port: int
    postgres_password: SecretStr
    postgres_db: str
    postgres_user: str = Field(default="postgres")
    
    app_mode: str = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)

    jwks_uri: str
    issuer: str
    jwt_algorithm: str = Field(default="RS256")
    jwt_audience: str
    jwt_scopes: str = Field(default="openid")
    keycloak_server_url: str
    
    # Helicone - Observabilidade
    helicone_api_key: SecretStr = Field(default=None)
    helicone_enabled: bool = Field(default=True)
    helicone_base_url: str = Field(default="https://oai.helicone.ai/v1")
    
    # OpenAI
    openai_api_key: SecretStr = Field(default=None)
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    
    @property
    def OPENAI_BASE_URL(self) -> str:
        """Get OpenAI base URL - uses Helicone if configured, otherwise direct OpenAI"""
        if self.helicone.is_configured:
            return self.helicone_base_url
        return self.openai_base_url
    
    @property
    def database(self) -> PostgresSettings:
        return PostgresSettings(
            postgres_host=self.postgres_host,
            postgres_port=self.postgres_port,
            postgres_password=self.postgres_password,
            postgres_db=self.postgres_db,
            postgres_user=self.postgres_user
        )
    
    @property
    def app(self) -> ApplicationSettings:
        return ApplicationSettings(
            app_mode=self.app_mode,
            app_host=self.app_host,
            app_port=self.app_port
        )
    
    @property
    def auth(self) -> AuthenticationSettings:
        return AuthenticationSettings(
            jwks_uri=f"{self.protocol}://{self.keycloak_server_url}/{self.jwks_uri}",
            issuer=f"{self.protocol}://{self.keycloak_server_url}/{self.issuer}",
            jwt_algorithm=self.jwt_algorithm,
            jwt_audience=self.jwt_audience,
            jwt_scopes=self.jwt_scopes.split()
        )
    
    @property
    def protocol(self) -> str:
        return "https" if self.app.is_production else "http"
    
    @property
    def helicone(self) -> HeliconeSettings:
        return HeliconeSettings(
            helicone_api_key=self.helicone_api_key,
            helicone_enabled=self.helicone_enabled,
            helicone_base_url=self.helicone_base_url
        )

settings = Settings()