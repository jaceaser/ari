import logging
from typing import Tuple, Optional
from backend.config.settings import get_prompt_config, get_classification_config, PromptConfig

class PromptClassifier:
    def __init__(self, openai_service):
        """
        Initialize the prompt classifier.
        
        Args:
            openai_service: Instance of AzureOpenAIService
        """
        self.openai_service = openai_service
        self.classification_config = get_classification_config()
        self.valid_categories = {'Education', 'Leads', 'Buyers', 'Attorneys', 
                               'Realtors', 'Title', 'HM Lenders', 'PM Lenders', 'Comps'}

    async def classify_prompt(self, prompt: str) -> str:
        """
        Classify the user's prompt into one of the predefined categories.
        
        Args:
            prompt: The user's input prompt
            
        Returns:
            str: The classified category (defaults to 'Education' if classification fails)
        """
        try:
            messages = [
                {
                    "role": "system",
                    "content": self.classification_config.system_message
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

            response = await self.openai_service.create_chat_completion(
                messages=messages,
                stream=False,
                temperature=0,
                max_tokens=10,
                model=self.classification_config.completion_model
            )

            classification = response.choices[0].message.content.strip()
            
            if classification not in self.valid_categories:
                logging.warning(f"Unexpected classification received: {classification}")
                return 'Education'
                
            return classification

        except Exception as e:
            logging.error(f"Error in prompt classification: {str(e)}")
            return 'Education'

    async def get_completion_config(self, prompt: str) -> Tuple[PromptConfig, str]:
        """
        Get the completion configuration and classification for a prompt.
        
        Args:
            prompt: The user's input prompt
            
        Returns:
            Tuple[PromptConfig, str]: The prompt configuration and classification
        """
        classification = await self.classify_prompt(prompt)
        config = get_prompt_config(classification)
        return config, classification

    async def generate_url(self, prompt: str, category: str) -> Optional[str]:
        """
        Generate a URL for data retrieval if the category supports it.
        
        Args:
            prompt: The user's input prompt
            category: The classified category
            
        Returns:
            Optional[str]: Generated URL or None if category doesn't support URL generation
        """
        config = get_prompt_config(category)
        
        if not config.url_generation_message or not config.url_generation_model:
            return None
            
        try:
            messages = [
                {
                    "role": "system",
                    "content": config.url_generation_message
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

            response = await self.openai_service.create_chat_completion(
                messages=messages,
                stream=False,
                temperature=0,
                max_tokens=200,
                model=config.url_generation_model
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logging.error(f"Error in URL generation: {str(e)}")
            return None