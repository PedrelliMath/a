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

settings = Settings()