"""
config.py — Central configuration for ET Investor Intelligence.
Loads all environment variables and defines system-wide constants.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # === LLM API Keys ===
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    groq_api_key: str = Field(default="", env="GROQ_API_KEY")
    elevenlabs_api_key: str = Field(default="", env="ELEVENLABS_API_KEY")

    # === Infrastructure ===
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/et_intelligence.db",
        env="DATABASE_URL"
    )

    # === App Config ===
    app_env: str = Field(default="development", env="APP_ENV")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    app_host: str = Field(default="0.0.0.0", env="APP_HOST")
    app_port: int = Field(default=8000, env="APP_PORT")

    model_config = {"env_file": ".env", "extra": "ignore"}


# === Singleton settings instance ===
settings = Settings()

# === External Data Source URLs ===
NSE_BHAVCOPY_BASE_URL = "https://archives.nseindia.com/content/historical/EQUITIES"
SEBI_BULK_DEAL_URL = "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doBulkDeal=yes"
SEBI_BLOCK_DEAL_URL = "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doBlockDeal=yes"
MONEYCONTROL_BASE_URL = "https://www.moneycontrol.com"

# === LLM Model Names ===
CLAUDE_MODEL = "claude-sonnet-4-20250514"
GEMINI_MODEL = "gemini-1.5-flash"
GROQ_MODEL = "llama-3.1-8b-instant"

# === Nifty 50 Symbols (NSE) ===
NIFTY50_SYMBOLS: List[str] = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA",
    "TITAN", "BAJFINANCE", "HCLTECH", "WIPRO", "ULTRACEMCO",
    "ONGC", "NTPC", "POWERGRID", "ADANIENT", "ADANIPORTS",
    "JSWSTEEL", "TATAMOTORS", "TATASTEEL", "M&M", "BAJAJFINSV",
    "COALINDIA", "DIVISLAB", "DRREDDY", "EICHERMOT", "GRASIM",
    "HEROMOTOCO", "HINDALCO", "INDUSINDBK", "NESTLEIND", "SBILIFE",
    "SHRIRAMFIN", "TECHM", "TRENT", "CIPLA", "APOLLOHOSP",
    "BPCL", "BRITANNIA", "HDFCLIFE", "BAJAJ-AUTO", "BEL"
]

# === Nifty Next 50 Symbols ===
NIFTY_NEXT50_SYMBOLS: List[str] = [
    "ABB", "ADANIGREEN", "ADANITRANS", "AMBUJACEM", "AUROPHARMA",
    "BANKBARODA", "BERGEPAINT", "BOSCHLTD", "CANBK", "CHOLAFIN",
    "COLPAL", "DABUR", "DLF", "DMART", "GAIL",
    "GODREJCP", "HAVELLS", "ICICIPRULI", "INDUSTOWER", "INDIGO",
    "IRCTC", "JINDALSTEL", "LUPIN", "MCDOWELL-N", "MOTHERSON",
    "MUTHOOTFIN", "NAUKRI", "NMDC", "PAGEIND", "PEL",
    "PIDILITIND", "PNB", "RECLTD", "SAIL", "SIEMENS",
    "SRF", "TORNTPHARM", "TVSMOTOR", "UBL", "VEDL",
    "VOLTAS", "WHIRLPOOL", "YESBANK", "ZOMATO", "JUBLFOOD",
    "LTIM", "MANKIND", "JSWENERGY", "VBL", "CUMMINSIND"
]

# === Sector → Symbol Mapping ===
SECTOR_SYMBOLS = {
    "IT": ["TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM"],
    "Banking": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK", "INDUSINDBK"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "COLPAL"],
    "Auto": ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN", "AUROPHARMA"],
    "Energy": ["RELIANCE", "ONGC", "BPCL", "NTPC", "POWERGRID", "GAIL"],
    "Metals": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "COALINDIA", "NMDC", "SAIL"],
    "Realty": ["DLF", "ADANIPORTS", "GODREJCP"],
    "Finance": ["BAJFINANCE", "BAJAJFINSV", "SBILIFE", "HDFCLIFE", "CHOLAFIN", "MUTHOOTFIN"],
}

# === Celery Schedule (IST = UTC+5:30) ===
# IST 18:00 = UTC 12:30, IST 18:30 = UTC 13:00, etc.
CELERY_SCHEDULE = {
    "daily_data_refresh": {"hour": 12, "minute": 30},       # 6:00 PM IST
    "scan_opportunity_radar": {"hour": 13, "minute": 0},    # 6:30 PM IST
    "scan_chart_patterns": {"hour": 13, "minute": 30},      # 7:00 PM IST
    "update_embeddings": {"hour": 14, "minute": 0},         # 7:30 PM IST
}
