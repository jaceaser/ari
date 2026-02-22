import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class SearchConfig:
    """Configuration for Azure Cognitive Search"""
    service: str
    key: str
    index: str
    endpoint: str
    query_type: str = "simple"
    semantic_search: bool = False
    semantic_config: str = ""
    content_columns: Optional[str] = None
    title_column: Optional[str] = None
    url_column: Optional[str] = None
    filename_column: Optional[str] = None
    vector_columns: Optional[str] = None
    enable_in_domain: bool = True
    top_k: int = 5
    strictness: int = 3
    embedding_deployment_name: Optional[str] = None
    embedding_endpoint: Optional[str] = None
    embedding_key: Optional[str] = None


@dataclass
class AzureConfig:
    """Configuration for Azure OpenAI connection"""
    resource: str
    endpoint: Optional[str]
    key: str
    deployment_name: str
    search_config: Optional[SearchConfig] = None


@dataclass
class PromptConfig:
    system_message: str
    azure_config: AzureConfig
    temperature: float = 0.0

    # Reasoning models (GPT-5 etc.)
    max_completion_tokens: Optional[int] = None

    top_p: float = 1.0
    stream: bool = True
    use_data: bool = False
    url_generation_message: Optional[str] = None
    url_generation_model: Optional[str] = None


# -----------------------------
# Azure Search Configuration
# -----------------------------
SEARCH_CONFIG = SearchConfig(
    service=os.environ.get("AZURE_SEARCH_SERVICE"),
    endpoint=os.environ.get("AZURE_SEARCH_API_ENDPOINT"),
    key=os.environ.get("AZURE_SEARCH_KEY"),
    index=os.environ.get("AZURE_SEARCH_INDEX"),
    query_type=os.environ.get("AZURE_SEARCH_QUERY_TYPE", "simple"),
    semantic_search=os.environ.get("AZURE_SEARCH_USE_SEMANTIC_SEARCH", "false").lower() == "true",
    semantic_config=os.environ.get("AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG", ""),
    content_columns=os.environ.get("AZURE_SEARCH_CONTENT_COLUMNS"),
    title_column=os.environ.get("AZURE_SEARCH_TITLE_COLUMN"),
    url_column=os.environ.get("AZURE_SEARCH_URL_COLUMN"),
    filename_column=os.environ.get("AZURE_SEARCH_FILENAME_COLUMN"),
    vector_columns=os.environ.get("AZURE_SEARCH_VECTOR_COLUMNS"),
    enable_in_domain=os.environ.get("AZURE_SEARCH_ENABLE_IN_DOMAIN", "true").lower() == "true",
    top_k=int(os.environ.get("AZURE_SEARCH_TOP_K", "5")),
    strictness=int(os.environ.get("AZURE_SEARCH_STRICTNESS", "3")),
    embedding_deployment_name=os.environ.get("AZURE_OPENAI_EMBEDDING_NAME"),
    embedding_endpoint=os.environ.get("AZURE_OPENAI_EMBEDDING_ENDPOINT"),
    embedding_key=os.environ.get("AZURE_OPENAI_EMBEDDING_KEY"),
)

CONTRACTS_SEARCH_CONFIG = SearchConfig(
    service=os.environ.get("AZURE_SEARCH_SERVICE"),
    endpoint=os.environ.get("AZURE_SEARCH_API_ENDPOINT"),
    key=os.environ.get("AZURE_SEARCH_KEY"),
    index=os.environ.get("AZURE_CONTRACTS_SEARCH_INDEX"),
    query_type=os.environ.get("AZURE_SEARCH_QUERY_TYPE", "simple"),
    semantic_search=os.environ.get("AZURE_SEARCH_USE_SEMANTIC_SEARCH", "false").lower() == "true",
    semantic_config=os.environ.get("AZURE_CONTRACTS_SEARCH_SEMANTIC_SEARCH_CONFIG", ""),
    content_columns=os.environ.get("AZURE_SEARCH_CONTENT_COLUMNS"),
    title_column=os.environ.get("AZURE_SEARCH_TITLE_COLUMN"),
    vector_columns=os.environ.get("AZURE_CONTRACTS_SEARCH_VECTOR_COLUMNS"),
    enable_in_domain=os.environ.get("AZURE_SEARCH_ENABLE_IN_DOMAIN", "true").lower() == "true",
    top_k=int(os.environ.get("AZURE_SEARCH_TOP_K", "5")),
    strictness=int(os.environ.get("AZURE_SEARCH_STRICTNESS", "3")),
    embedding_deployment_name=os.environ.get("AZURE_OPENAI_EMBEDDING_NAME"),
    embedding_endpoint=os.environ.get("AZURE_OPENAI_EMBEDDING_ENDPOINT"),
    embedding_key=os.environ.get("AZURE_OPENAI_EMBEDDING_KEY"),
)

# BUYERS_CONFIG = SearchConfig(
#     service=os.environ.get("AZURE_SEARCH_SERVICE"),
#     key=os.environ.get("AZURE_SEARCH_KEY"),
#     index=os.environ.get("AZURE_LEADS_SEARCH_INDEX"),
#     query_type=os.environ.get("AZURE_SEARCH_QUERY_TYPE", "simple"),
#     semantic_search=os.environ.get("AZURE_SEARCH_USE_SEMANTIC_SEARCH", "false").lower() == "true",
#     semantic_config=os.environ.get("AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG", ""),
#     content_columns=os.environ.get("AZURE_SEARCH_CONTENT_COLUMNS"),
#     title_column=os.environ.get("AZURE_SEARCH_TITLE_COLUMN"),
#     url_column=os.environ.get("AZURE_SEARCH_URL_COLUMN"),
#     filename_column=os.environ.get("AZURE_SEARCH_FILENAME_COLUMN"),
#     vector_columns=os.environ.get("AZURE_SEARCH_VECTOR_COLUMNS"),
#     enable_in_domain=os.environ.get("AZURE_SEARCH_ENABLE_IN_DOMAIN", "true").lower() == "true",
#     top_k=int(os.environ.get("AZURE_SEARCH_TOP_K", "5")),
#     strictness=int(os.environ.get("AZURE_SEARCH_STRICTNESS", "3")),
#     embedding_deployment_name=os.environ.get("AZURE_OPENAI_EMBEDDING_NAME"),
#     embedding_endpoint=os.environ.get("AZURE_OPENAI_EMBEDDING_ENDPOINT"),
#     embedding_key=os.environ.get("AZURE_OPENAI_EMBEDDING_KEY"),
# )


# -----------------------------
# Azure OpenAI Configurations
# -----------------------------
BASE_AZURE_CONFIG = AzureConfig(
    resource=os.environ.get("AZURE_OPENAI_RESOURCE"),
    endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    key=os.environ.get("AZURE_OPENAI_KEY"),
    deployment_name=os.environ.get("AZURE_OPENAI_MODEL"),  # reasoning model
    search_config=SEARCH_CONFIG,
)

BUYERS_AZURE_CONFIG = AzureConfig(
    resource=os.environ.get("AZURE_OPENAI_RESOURCE"),
    endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    key=os.environ.get("AZURE_OPENAI_KEY"),
    deployment_name=os.environ.get("AZURE_OPENAI_MODEL"),  # reasoning model
    # search_config=BUYERS_CONFIG,
)

# Mini model
CLASSIFICATION_AZURE_CONFIG = AzureConfig(
    resource=os.environ.get("AZURE_OPENAI_RESOURCE"),
    endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    key=os.environ.get("AZURE_OPENAI_KEY"),
    deployment_name=os.environ.get("AZURE_OPENAI_CLASSIFICATION_MODEL", "gpt-35-turbo-16k"),
)

CONTRACT_AZURE_CONFIG = AzureConfig(
    resource=os.environ.get("AZURE_OPENAI_RESOURCE"),
    endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    key=os.environ.get("AZURE_OPENAI_KEY"),
    deployment_name=os.environ.get("AZURE_OPENAI_MODEL"),  # reasoning model
    search_config=CONTRACTS_SEARCH_CONFIG,
)


# Helpers for token defaults
_DEFAULT_COMPLETION_TOKENS = int(
    os.environ.get(
        "AZURE_OPENAI_MAX_COMPLETION_TOKENS",
        os.environ.get("AZURE_OPENAI_MAX_TOKENS", 1000),
    )
)

_STREAM_DEFAULT = os.environ.get("AZURE_OPENAI_STREAM", "true").lower() == "true"


# -----------------------------
# Prompt Configurations
# -----------------------------
PROMPT_CONFIGS = {
    # Reasoning model (AZURE_OPENAI_MODEL)
    "Education": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_SYSTEM_MESSAGE",
            "You are an AI assistant that helps people find information.",
        ),
        azure_config=BASE_AZURE_CONFIG,
        temperature=0.2,
        max_completion_tokens=_DEFAULT_COMPLETION_TOKENS,
        stream=_STREAM_DEFAULT,
        use_data=True,
    ),

    # Reasoning model (AZURE_OPENAI_MODEL)
    "Leads": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_LEADS_SYSTEM_MESSAGE",
            "You are an AI assistant analyzing lead data...",
        ),
        azure_config=BASE_AZURE_CONFIG,
        temperature=0.7,
        max_completion_tokens=4000,
        stream=_STREAM_DEFAULT,  # ✅ only defined once (no duplicate)
        use_data=False,
    ),

    # Mini model (classification/linking)
    "LeadsLink": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_LEAD_LINK_MESSAGE",
            "You are an AI assistant analyzing lead data...",
        ),
        azure_config=CLASSIFICATION_AZURE_CONFIG,
        temperature=0.7,
        max_completion_tokens=4000,
        stream=False,
        use_data=False,
    ),

    # Reasoning model (AZURE_OPENAI_MODEL)
    "Attorneys": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_ATTORNEYS_SYSTEM_MESSAGE",
            "You are an AI assistant analyzing attorneys data...",
        ),
        azure_config=BASE_AZURE_CONFIG,
        temperature=0.7,
        max_completion_tokens=4000,
        stream=_STREAM_DEFAULT,
        use_data=False,
    ),

    # Mini model
    "AttorneysLink": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_ATTORNEY_LINK_MESSAGE",
            "You are an AI assistant analyzing attorneys data...",
        ),
        azure_config=CLASSIFICATION_AZURE_CONFIG,
        temperature=0.7,
        max_completion_tokens=4000,
        stream=False,
        use_data=False,
    ),

    # Mini model
    "Title": PromptConfig(
        system_message="Summarize the conversation so far into a 4-word or less title...",
        azure_config=CLASSIFICATION_AZURE_CONFIG,
        temperature=1,
        max_completion_tokens=64,
        stream=False,
        use_data=False,
    ),

    # Mini model
    "Classification": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_CLASSIFICATION_SYSTEM_MESSAGE",
            "You are an AI classifier that categorizes user queries...",
        ),
        azure_config=CLASSIFICATION_AZURE_CONFIG,
        temperature=0.2,
        max_completion_tokens=20,
        stream=False,
        use_data=False,
    ),

    # Mini model
    "PropertyLink": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_COMP_SUBJ_PROPERTY_LINK_MESSAGE",
            "You are a URL generator that generates a zillow link for the address given...",
        ),
        azure_config=CLASSIFICATION_AZURE_CONFIG,
        temperature=0.2,
        max_completion_tokens=200,
        stream=False,
        use_data=False,
    ),

    # Mini model
    "CompLink": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_COMP_PROPERTIES_LINK_MESSAGE",
            "You are a URL generator that generates a zillow link for comps similar to this address...",
        ),
        azure_config=CLASSIFICATION_AZURE_CONFIG,
        temperature=0.2,
        max_completion_tokens=200,
        stream=False,
        use_data=False,
    ),

    # Reasoning model (AZURE_OPENAI_MODEL)
    "Comps": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_COMP_PROPERTIES_MESSAGE",
            "You are a URL generator that generates a zillow link for comps similar to this address...",
        ),
        azure_config=BASE_AZURE_CONFIG,
        temperature=0.2,
        max_completion_tokens=4000,
        stream=True,
        use_data=False,
    ),

    # Reasoning model (AZURE_OPENAI_MODEL)
    "Contracts": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_CONTRACTS_MESSAGE",
            "You are an AI Real Estate assistant that writes contracts related to real estate transactions.",
        ),
        azure_config=CONTRACT_AZURE_CONFIG,
        temperature=float(os.environ.get("AZURE_OPENAI_TEMPERATURE", 0)),
        max_completion_tokens=_DEFAULT_COMPLETION_TOKENS,
        stream=_STREAM_DEFAULT,
        use_data=True,
    ),

    # Mini model
    "ContractsExpansion": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_CONTRACTS_EXPANSION_MESSAGE",
            "You enhance legal contract prompts for drafting assistants.",
        ),
        azure_config=CLASSIFICATION_AZURE_CONFIG,
        temperature=0.4,
        max_completion_tokens=800,
        stream=False,
        use_data=False,
    ),

    # Mini model
    "CityStateExtraction": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_CITY_STATE_PROMPT",
            "Extract the city and state",
        ),
        azure_config=CLASSIFICATION_AZURE_CONFIG,
        temperature=0.4,
        max_completion_tokens=800,
        stream=False,
        use_data=False,
    ),

    # Reasoning model (AZURE_OPENAI_MODEL)
    "Buyers": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_BUYERS_SYSTEM_MESSAGE",
            "You are an AI assistant that helps people find information.",
        ),
        azure_config=BUYERS_AZURE_CONFIG,
        temperature=float(os.environ.get("AZURE_OPENAI_TEMPERATURE", 0)),
        max_completion_tokens=_DEFAULT_COMPLETION_TOKENS,
        stream=_STREAM_DEFAULT,
        use_data=False,
    ),

    # Reasoning model (AZURE_OPENAI_STRATEGY_MODEL)
    "Strategy": PromptConfig(
        system_message=os.environ.get("AZURE_OPENAI_STRATEGY_PROMPT"),
        azure_config=AzureConfig(
            resource=os.environ.get("AZURE_OPENAI_RESOURCE"),
            endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
            key=os.environ.get("AZURE_OPENAI_KEY"),
            deployment_name=os.environ.get("AZURE_OPENAI_STRATEGY_MODEL"),
        ),
        temperature=0.3,
        max_completion_tokens=16000,
        stream=True,
        use_data=False,  # No grounding allowed
    ),

    "OffTopic": PromptConfig(
        system_message=os.environ.get(
            "AZURE_OPENAI_OFFTOPIC_MESSAGE",
            "This prompt is off-topic, and as ARI, I cannot provide further information. "
            "Please ask a question related to real estate, strategy, education, or lead generation.",
        ),
        azure_config=BASE_AZURE_CONFIG,
        temperature=0.0,
        max_completion_tokens=512,
        stream=False,
        use_data=False,
    ),
}


# -----------------------------
# CosmosDB Settings (kept as-is)
# -----------------------------
COSMOS_DB = {
    "ACCOUNT": os.environ.get("AZURE_COSMOSDB_ACCOUNT"),
    "KEY": os.environ.get("AZURE_COSMOSDB_ACCOUNT_KEY"),
    "DATABASE": os.environ.get("AZURE_COSMOSDB_DATABASE"),
    "CONVERSATIONS_CONTAINER": os.environ.get("AZURE_COSMOSDB_CONVERSATIONS_CONTAINER"),
    "LEADGEN_DATABASE": os.environ.get("AZURE_COSMOSDB_LEADGEN_DATABASE"),
    "LEADGEN_CONTAINER": os.environ.get("AZURE_COSMOSDB_LEADGEN_CONTAINER"),
    "BUYERS_DATABASE": os.environ.get("AZURE_COSMOSDB_BUYERS_DATABASE"),
    "NATIONWIDE_BUYERS_CONTAINER": os.environ.get("AZURE_COSMOSDB_NATIONWIDE_BUYERS_CONTAINER"),
    "ENABLE_FEEDBACK": os.environ.get("AZURE_COSMOSDB_ENABLE_FEEDBACK", "false").lower() == "true",
}


# -----------------------------
# Teachable Settings
# -----------------------------
TEACHABLE = {
    "CLIENT_ID": os.environ.get("CLIENT_ID"),
    "CLIENT_SECRET": os.environ.get("CLIENT_SECRET"),
    "AUTHORIZATION_URL": os.environ.get("AUTHORIZATION_URL"),
    "TOKEN_URL": os.environ.get("TOKEN_URL"),
    "REDIRECT_URI": os.environ.get("REDIRECT_URI"),
    "USER_INFO_URL": os.environ.get("USER_INFO_URL"),
}


# -----------------------------
# UI Configuration (kept as-is)
# -----------------------------
UI_CONFIG = {
    "auth_enabled": os.environ.get("AUTH_ENABLED", "true").lower() == "false",
    "feedback_enabled": (os.environ.get("AZURE_COSMOSDB_ENABLE_FEEDBACK", "false").lower() == "true"),
    "ui": {
        "title": os.environ.get("UI_TITLE", "ARI"),
        "logo": os.environ.get("UI_LOGO", "/assets/UC-logo-3.png"),
        "chat_logo": os.environ.get("UI_CHAT_LOGO", "/assets/uc-ai-logo.png"),
        "chat_title": os.environ.get("UI_CHAT_TITLE", "ARI"),
        "chat_description": os.environ.get("UI_CHAT_DESCRIPTION", "Ask ARI anything about Real Estate Investing and taking deals down!"),
        "favicon": os.environ.get("UI_FAVICON", "/favicon.ico"),
        "show_share_button": os.environ.get("UI_SHOW_SHARE_BUTTON", "true").lower() == "true",
        "version": "v0.9.240125-BETA",
    },
}


AZURE_BLOB = {
    "ACCOUNT_NAME": os.environ.get("AZURE_BLOB_ACCOUNT_NAME"),
    "ACCOUNT_KEY": os.environ.get("AZURE_BLOB_ACCOUNT_KEY"),
}

SCRAPING_BEE_API_KEY = os.environ.get("SCRAPING_BEE_API_KEY")
EXA_API_KEY = os.environ.get("EXA_API_KEY")

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
ENVIRONMENT = os.environ.get("ENVIRONMENT")

# LemonSqueezy API Configuration
LEMONSQUEEZY_API_KEY = os.environ.get("LEMONSQUEEZY_API_KEY")
LEMONSQUEEZY_STORE_NAME = os.environ.get("LEMONSQUEEZY_STORE_NAME")
LEMONSQUEEZY_WEBHOOK_SECRET = os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET")

# Email Settings for Magic Links
SMTP_SERVER = os.environ.get("SMTP_SERVER")
SMTP_PORT = os.environ.get("SMTP_PORT")
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
FROM_EMAIL = os.environ.get("FROM_EMAIL")

# Redis Configuration
REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")

HOST_URL = os.environ.get("HOST_URL")

# Security
SECRET_KEY = os.environ.get("SECRET_KEY")


def init_app_config(app):
    """Initialize application configuration"""
    app.config.update(
        UI_CONFIG=UI_CONFIG,
        COSMOS_DB=COSMOS_DB,
        TEACHABLE=TEACHABLE,
        PROMPT_CONFIGS=PROMPT_CONFIGS,
        AZURE_BLOB=AZURE_BLOB,
        SCRAPING_BEE_API_KEY=SCRAPING_BEE_API_KEY,
        EXA_API_KEY=EXA_API_KEY,
        DISCORD_WEBHOOK_URL=DISCORD_WEBHOOK_URL,
        ENVIRONMENT=ENVIRONMENT,
        SEARCH_CONFIG=SEARCH_CONFIG,

        # LemonSqueezy Configuration
        LEMONSQUEEZY_API_KEY=LEMONSQUEEZY_API_KEY,
        LEMONSQUEEZY_STORE_NAME=LEMONSQUEEZY_STORE_NAME,
        LEMONSQUEEZY_WEBHOOK_SECRET=LEMONSQUEEZY_WEBHOOK_SECRET,

        # Email Configuration
        SMTP_SERVER=SMTP_SERVER,
        SMTP_PORT=SMTP_PORT,
        SMTP_USERNAME=SMTP_USERNAME,
        SMTP_PASSWORD=SMTP_PASSWORD,
        FROM_EMAIL=FROM_EMAIL,

        # Redis Configuration
        REDIS_HOST=REDIS_HOST,
        REDIS_PORT=REDIS_PORT,
        REDIS_PASSWORD=REDIS_PASSWORD,

        HOST_URL=HOST_URL,

        # Security Configuration
        SECRET_KEY=SECRET_KEY,
    )