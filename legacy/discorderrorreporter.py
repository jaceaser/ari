from functools import wraps
import logging
import traceback
from datetime import datetime
from typing import Dict, Any
import aiohttp
import json

class DiscordErrorReporter:
    def __init__(self, webhook_url: str, environment: str = "production"):
        self.webhook_url = webhook_url
        self.environment = environment
        
        # Configure logging
        logging.basicConfig(
            level=logging.ERROR,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('error_logs.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def format_error_message(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """Format error details into a Discord message."""
        timestamp = datetime.now().isoformat()
        error_traceback = traceback.format_exc()
        
        # Create Discord embed
        embed = {
            "title": f"🚨 Error Alert - {type(error).__name__}",
            "description": str(error),
            "color": 15158332,  # Red color
            "fields": [
                {
                    "name": "Environment",
                    "value": self.environment,
                    "inline": True
                },
                {
                    "name": "User ID",
                    "value": context.get('user_id', 'N/A'),
                    "inline": True
                },
                {
                    "name": "Conversation ID",
                    "value": context.get('conversation_id', 'N/A'),
                    "inline": True
                },
                {
                    "name": "Timestamp",
                    "value": timestamp,
                    "inline": False
                },
                {
                    "name": "Error Traceback",
                    "value": f"```python\n{error_traceback[:1000]}```",  # Discord has a 1024 char limit per field
                    "inline": False
                }
            ],
            "footer": {
                "text": "Real Estate AI Chat Error Reporting"
            }
        }

        # Add any additional context as fields
        for key, value in context.items():
            if key not in ['user_id', 'conversation_id']:
                embed["fields"].append({
                    "name": key,
                    "value": str(value)[:1000],  # Truncate long values
                    "inline": False
                })

        return {
            "content": "⚠️ New Error Detected",
            "embeds": [embed]
        }

    async def send_discord_alert(self, error_message: Dict[str, Any]) -> None:
        """Send error report to Discord webhook."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=error_message,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 204:  # Discord returns 204 on success
                        response_text = await response.text()
                        self.logger.error(f"Failed to send Discord alert. Status: {response.status}, Response: {response_text}")
                    else:
                        self.logger.info("Discord alert sent successfully")
        except Exception as e:
            self.logger.error(f"Failed to send Discord alert: {str(e)}")

    async def report_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Log error and send Discord alert."""
        error_message = self.format_error_message(error, context)
        
        # Log to file
        self.logger.error(f"Error: {str(error)}\nContext: {json.dumps(context, indent=2)}")
        
        # Send Discord alert
        await self.send_discord_alert(error_message)

def discord_error_handler(error_reporter: DiscordErrorReporter):
    """Decorator for error handling in websocket endpoints."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                context = {
                    'function': func.__name__,
                    'args': str(args),
                    'kwargs': str(kwargs),
                    'timestamp': datetime.now().isoformat()
                }
                await error_reporter.report_error(e, context)
                raise  # Re-raise the exception after reporting
        return wrapper
    return decorator