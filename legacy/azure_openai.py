from typing import Optional, Dict, AsyncGenerator
from openai import AsyncAzureOpenAI
from backend.config.settings import PromptConfig
from backend.utils.formatting import parse_multi_columns
from backend.utils.discorderrorreporter import DiscordErrorReporter
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
import logging
import re
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
import json

_STOP = {
    "the","a","an","and","or","to","of","in","for","with","on","at","by","from",
    "please","show","tell","explain","give","make","create","return","format",
    "context","question","answer"
}

def _build_retrieval_query(text: str, max_terms: int = 18) -> str:
    """
    Turn a verbose user prompt into a short keywordy query for BM25.
    """
    t = text.lower()

    # keep IDs / numbers that often matter
    nums = re.findall(r"\b\d{3,}\b", t)

    words = re.findall(r"[a-z0-9]{3,}", t)
    words = [w for w in words if w not in _STOP]

    # de-dup preserve order
    seen = set()
    terms = []
    for w in nums + words:
        if w not in seen:
            seen.add(w)
            terms.append(w)

    return " ".join(terms[:max_terms])


class AzureOpenAIService:
    def __init__(self, config, discord_reporter: DiscordErrorReporter, AISearchAPIKey: str, AISearchEndpoint: str, AISearchSemanticConfig: str):
        self.config = config
        self.client = None
        self.discord_reporter = discord_reporter
        self.AISearchClientCredential = AzureKeyCredential(AISearchAPIKey)
        self.AISearchEndpoint = AISearchEndpoint
        self.AISearchSemanticConfig = AISearchSemanticConfig
    
    async def init_client(self, prompt_config: PromptConfig):
        """Initialize Azure OpenAI client using PromptConfig"""
        try:
            azure_config = prompt_config.azure_config
            endpoint = azure_config.endpoint or f"https://{azure_config.resource}.openai.azure.com/"
            
            # Authentication
            ad_token_provider = None
            if not azure_config.key:
                ad_token_provider = get_bearer_token_provider(
                    DefaultAzureCredential(), 
                    "https://cognitiveservices.azure.com/.default"
                )

            # TEST: Dynamically pick the right API version
            model_name = azure_config.deployment_name.lower()
            selected_api_version = "2024-12-01-preview" # 2025-01-31 2024-12-01-preview

            client_config = {

                # "api_version": "2024-06-01",
                "api_version": selected_api_version,
                "api_key": azure_config.key,
                "azure_ad_token_provider": ad_token_provider,
            }

            self.client = AsyncAzureOpenAI(azure_endpoint=endpoint, **client_config)
                
            return self.client

        except Exception as e:
            logging.error(f"Error initializing Azure OpenAI client: {str(e)}")
            raise

    def _get_data_source(self, prompt_config: PromptConfig) -> Optional[Dict]:
        """Build the Azure Search data source config if required."""
        azure_config = prompt_config.azure_config
        search_config = azure_config.search_config

        if not prompt_config.use_data or not search_config:
            return None

        # Set up authentication block
        authentication = (
            {"type": "api_key", "key": search_config.key}
            if search_config.key
            else {"type": "SystemAssignedManagedIdentity"}
        )

        # Base parameters block
        parameters = {
            "endpoint": f"https://{search_config.service}.search.windows.net",
            "authentication": authentication,
            "index_name": search_config.index,
            "fields_mapping": {
                "content_fields": parse_multi_columns(search_config.content_columns) if search_config.content_columns else [],
                "title_field": search_config.title_column,
                "url_field": search_config.url_column,
                "filepath_field": search_config.filename_column,
                "vector_fields": parse_multi_columns(search_config.vector_columns) if search_config.vector_columns else []
            },
            "in_scope": search_config.enable_in_domain,
            "top_n_documents": search_config.top_k,
            "query_type": search_config.query_type,
            "semantic_configuration": search_config.semantic_config,
            "strictness": search_config.strictness
        }

        # Base data source object
        data_source = {
            "type": "azure_search",
            "parameters": parameters
        }

        # Add embedding dependency if vector search is used
        if "vector" in search_config.query_type.lower():
            if search_config.embedding_deployment_name:
                embedding_dependency = {
                    "type": "deployment_name",
                    "deployment_name": search_config.embedding_deployment_name
                }
            elif search_config.embedding_endpoint and search_config.embedding_key:
                embedding_dependency = {
                    "type": "Endpoint",
                    "endpoint": search_config.embedding_endpoint,
                    "authentication": {
                        "type": "APIKey",
                        "key": search_config.embedding_key
                    }
                }
            else:
                raise Exception("Vector query type selected but no embedding dependency configured")

            parameters["embedding_dependency"] = embedding_dependency

        return data_source

    async def create_chat_completion(self, messages, prompt_config: PromptConfig):
        """Non-reasoning / legacy path (kept as-is)."""
        try:
            await self.init_client(prompt_config)

            # clean id
            messages = [{"role": msg["role"], "content": msg["content"]} for msg in messages]

            model_args = {
                "model": prompt_config.azure_config.deployment_name,
                "messages": messages,
                "top_p": prompt_config.top_p,
                "stream": prompt_config.stream,
            }

            response = await self.client.chat.completions.create(**model_args)

            if prompt_config.stream:
                async for chunk in response:
                    yield chunk
            else:
                yield response

        except Exception as e:
            logging.error(f"Error in chat completion: {str(e)}")
            error_context = {
                "service": "AzureOpenAIService",
                "method": "create_chat_completion",
                "deployment": prompt_config.azure_config.deployment_name,
                "last_message": messages[-1] if messages else None,
            }
            logging.error(f"Context: {error_context}")
            raise

    async def create_reasoning_chat_completion(self, messages, prompt_config: PromptConfig):
        """
        Reasoning path for GPT-5 deployments.
        Key differences:
        - MUST use max_completion_tokens (NOT max_tokens)
        - Put max_completion_tokens into extra_body to avoid any SDK remapping quirks
        - Merge extra_body with data_sources safely
        """
        try:
            await self.init_client(prompt_config)

            messages = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
            prompt = messages[-1]["content"]

            model_args = {
                "model": prompt_config.azure_config.deployment_name,
                "messages": messages,
                "top_p": prompt_config.top_p,
                "stream": prompt_config.stream,
            }

            # ✅ Add max_completion_tokens as TOP-LEVEL
            if prompt_config.max_completion_tokens is not None:
                model_args["max_completion_tokens"] = prompt_config.max_completion_tokens

            # Grounding stays in extra_body
            # extra_body = {}
            if prompt_config.use_data:
                data_source = self._get_data_source(prompt_config)
                context = await self.retrieve_search_results(prompt, prompt_config, data_source['parameters']['index_name'])
                messages[-1]["content"] = f"Context:\n{context}\n\n---\n\nQuestion: {prompt}"
            
            response = await self.client.chat.completions.create(**model_args)

            if prompt_config.stream:
                async for chunk in response:
                    yield chunk
            else:
                yield response

        except Exception as e:
            logging.error(f"Error in reasoning chat completion: {str(e)}")
            error_context = {
                "service": "AzureOpenAIService",
                "method": "create_reasoning_chat_completion",
                "deployment": prompt_config.azure_config.deployment_name,
                "last_message": messages[-1] if messages else None,
            }
            logging.error(f"Context: {error_context}")
            raise

    async def generate_title(self, conversation_messages):
        """Generate a title using the Title config"""
        try:
            # Create messages array with all conversation messages
            messages = [{'role': msg['role'], 'content': msg['content']} 
                    for msg in conversation_messages]
            # Add system message at the beginning
            messages.insert(0, {
                'role': 'system',
                'content': self.config['Title'].system_message
            })
            
            async for response in self.create_chat_completion(
                messages=messages,
                prompt_config=self.config['Title']  # Use Title config directly from constructor config
            ):
                return response.choices[0].message.content.strip()

        except Exception as e:
            logging.error(f"Error generating title: {str(e)}")
            return (messages[1]['content'] if len(messages) > 1 
                    else "New Conversation")  # Skip system message when getting fallback

    async def generate_lead_url(self, prompt_config:PromptConfig, prompt: str) -> str:
        """
        Generate a URL for lead generation based on the prompt.
        
        Args:
            prompt: User's input prompt
            
        Returns:
            str: Generated URL for lead scraping
            
        Raises:
            Exception: If URL generation fails
        """
        try:
            messages = [
                {
                    "role": "system",
                    "content": prompt_config.system_message
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            async for response in self.create_chat_completion(
                messages=messages,
                prompt_config=prompt_config
            ):
                return response.choices[0].message.content.strip()

        except Exception as e:
            logging.error(f"Error generating lead URL: {str(e)}")
            raise
    async def retrieve_search_results(self, prompt: str, prompt_config: PromptConfig, index_name: str) -> str:
        """
        Hybrid (BM25 + vector) + semantic rerank.
        Returns JSON text blob of top context chunks.
        """
        sc = SearchClient(
            endpoint=self.AISearchEndpoint,
            index_name=index_name,
            credential=self.AISearchClientCredential,
        )

        # --- 1) Build retrieval query (BM25)
        user_question = prompt
        retrieval_query = _build_retrieval_query(user_question)

        # --- 2) Determine vector field + embedding deployment
        search_config = prompt_config.azure_config.search_config
        vector_fields = parse_multi_columns(search_config.vector_columns) if search_config.vector_columns else []
        vector_field = vector_fields[0] if vector_fields else "vector"  # fallback

        embedding_deployment = search_config.embedding_deployment_name
        if not embedding_deployment:
            raise Exception("Hybrid search requires search_config.embedding_deployment_name (embedding deployment).")

        # --- 3) Get query embedding (embed the natural language question)
        if not self.client:
            await self.init_client(prompt_config)

        emb = await self.client.embeddings.create(
            model=embedding_deployment,   # Azure OpenAI *deployment name*
            input=user_question
        )
        query_embedding = emb.data[0].embedding

        vector = VectorizedQuery(
            vector=query_embedding,
            k_nearest_neighbors=50,
            fields=vector_field,
        )

        # --- 4) Run hybrid + semantic
        sr = sc.search(
            search_text=retrieval_query,
            search_fields=["chunk", "title", "tags", "topics"],
            vector_queries=[vector],

            query_type="semantic",
            semantic_configuration_name=self.AISearchSemanticConfig,
            semantic_query=user_question,

            top=25,

            query_caption="extractive",
            query_answer="extractive",

            select=["filename", "topics", "chunk", "title", "tags"],
        )

        ctx_objects = []
        for d in sr:
            txt = d.get("chunk") or ""
            if not txt:
                continue

            ctx_objects.append({
                "chunked_content": txt,
                "filename": (d.get("filename") or "").strip(),
                "topics": d.get("topics") or [],
                "tags": d.get("tags") or [],
                "title": d.get("title") or ""
            })

        return json.dumps({"context": ctx_objects}, ensure_ascii=False, indent=2)
