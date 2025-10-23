from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

MAX_MINUTES_TO_ASSUMING_IS_LIVE = 4 * 60

class Settings(BaseSettings):
    # Settings
    GEMINI_API_KEY : str
    MODEL : Optional[str] = "gemini/gemini-2.5-flash"


    class Config:
        env_prefix = ""
        case_sensitive = False


# Create a settings instance
settings = Settings()