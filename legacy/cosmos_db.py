import uuid
import logging
import asyncio
import certifi
import os
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from azure.cosmos.aio import CosmosClient
from azure.cosmos import exceptions

class CosmosDBService:
    """Main service class that wraps both conversation and lead generation clients"""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.conversation_client = None
        self.leadgen_client = None
        self.buyers_client = None
        self._init_clients()

    def _init_clients(self) -> None:
        """Initialize both cosmos clients"""
        cosmos_endpoint = f'https://{self.config["ACCOUNT"]}.documents.azure.com:443/'
        
        os.environ['SSL_CERT_FILE'] = certifi.where()
        # Initialize conversation client if configured
        if (self.config["DATABASE"] and self.config["CONVERSATIONS_CONTAINER"]):
            self.conversation_client = CosmosConversationClient(
                cosmosdb_endpoint=cosmos_endpoint,
                credential=self.config["KEY"],
                database_name=self.config["DATABASE"],
                container_name=self.config["CONVERSATIONS_CONTAINER"],
                enable_message_feedback=self.config["ENABLE_FEEDBACK"]
            )

        # Initialize leadgen client if configured
        if (self.config["LEADGEN_DATABASE"] and self.config["LEADGEN_CONTAINER"]):
            self.leadgen_client = CosmosLeadGenClient(
                cosmosdb_endpoint=cosmos_endpoint,
                credential=self.config["KEY"],
                database_name=self.config["LEADGEN_DATABASE"],
                container_name=self.config["LEADGEN_CONTAINER"]
            )
        # Initialize buyers client if configured
        if (self.config.get("BUYERS_DATABASE") and self.config.get("NATIONWIDE_BUYERS_CONTAINER")):
            self.buyers_client = CosmosBuyersClient(
                cosmosdb_endpoint=cosmos_endpoint,
                credential=self.config["KEY"],
                database_name=self.config["BUYERS_DATABASE"],
                container_name=self.config["NATIONWIDE_BUYERS_CONTAINER"]
            )

    async def ensure(self) -> Tuple[bool, str]:
        """Verify both clients are working"""
        if self.conversation_client:
            conv_success, conv_msg = await self.conversation_client.ensure()
            if not conv_success:
                return False, conv_msg

        # if self.leadgen_client:
        #     lead_success = await self.leadgen_client.ensure()
        #     if not lead_success:
        #         return False, "LeadGen client initialization failed"

        return True, "All clients initialized successfully"

    # Delegate conversation methods to conversation_client
    async def create_conversation(self, user_id: str, title: str = '') -> Dict:
        return await self.conversation_client.create_conversation(user_id, title)

    async def get_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict]:
        return await self.conversation_client.get_conversation(user_id, conversation_id)

    async def get_conversations(self, user_id: str, limit: int, offset: int = 0) -> List[Dict]:
        return await self.conversation_client.get_conversations(user_id, limit, offset=offset)

    async def delete_conversation(self, user_id: str, conversation_id: str) -> Any:
        return await self.conversation_client.delete_conversation(user_id, conversation_id)

    async def create_message(self, uuid: str, conversation_id: str, user_id: str, input_message: Dict) -> Dict:
        return await self.conversation_client.create_message(uuid, conversation_id, user_id, input_message)

    async def get_messages(self, user_id: str, conversation_id: str) -> List[Dict]:
        return await self.conversation_client.get_messages(user_id, conversation_id)

    async def update_message_feedback(self, user_id: str, message_id: str, feedback: str) -> Dict:
        return await self.conversation_client.update_message_feedback(user_id, message_id, feedback)

    async def delete_messages(self, conversation_id: str, user_id: str) -> List[Dict]:
        return await self.conversation_client.delete_messages(conversation_id, user_id)

    # Delegate lead generation methods to leadgen_client
    async def get_cached_data(self, url: str) -> Optional[Dict]:
        return await self.leadgen_client.get_cached_data(url)

    async def write_to_cache(self, url: str, data: List[Dict], timestamp: str) -> None:
        await self.leadgen_client.write_to_cache(url, data, timestamp)
    
    # Delegate buyer methods to buyers_client
    async def get_buyers_by_city_state(self, city: str, state: str, max_results: int = 50) -> List[Dict]:
        if not self.buyers_client:
            logging.error("Buyers client is not initialized")
            return []
        return await self.buyers_client.get_buyers_by_city_state(city, state, max_results)


class CosmosConversationClient:
    """Handles conversation-related operations in CosmosDB"""
    def __init__(self, cosmosdb_endpoint: str, credential: any, database_name: str, 
                 container_name: str, enable_message_feedback: bool = False):
        self.cosmosdb_endpoint = cosmosdb_endpoint
        self.credential = credential
        self.database_name = database_name
        self.container_name = container_name
        self.enable_message_feedback = enable_message_feedback
        
        try:
            self.cosmosdb_client = CosmosClient(self.cosmosdb_endpoint, credential=credential)
        except exceptions.CosmosHttpResponseError as e:
            if e.status_code == 401:
                logging.error(f"Invalid credentials: {e}")
            else:
                logging.error(f"Invalid CosmosDB endpoint: {e}")
            raise

        try:
            self.database_client = self.cosmosdb_client.get_database_client(database_name)
        except exceptions.CosmosResourceNotFoundError as e:
            logging.error(f"Invalid CosmosDB database name: {e}")
            raise

        try:
            self.container_client = self.database_client.get_container_client(container_name)
        except exceptions.CosmosResourceNotFoundError as e:
            logging.error(f"Invalid CosmosDB container name: {e}")
            raise

    async def ensure(self):
        if not self.cosmosdb_client or not self.database_client or not self.container_client:
            return False, "CosmosDB client not initialized correctly"
            
        try:
            database_info = await self.database_client.read()
        except Exception as e:
            return False, f"CosmosDB database {self.database_name} on account {self.cosmosdb_endpoint} not found"
        
        try:
            container_info = await self.container_client.read()
        except:
            return False, f"CosmosDB container {self.container_name} not found"
            
        return True, "CosmosDB client initialized successfully"

    async def create_conversation(self, user_id, title = ''):
        conversation = {
            'id': str(uuid.uuid4()),  
            'type': 'conversation',
            'createdAt': datetime.utcnow().isoformat(),  
            'updatedAt': datetime.utcnow().isoformat(),  
            'userId': user_id,
            'title': title
        }
        ## TODO: add some error handling based on the output of the upsert_item call
        resp = await self.container_client.upsert_item(conversation)  
        if resp:
            return resp
        else:
            return False
    
    async def upsert_conversation(self, conversation):
        resp = await self.container_client.upsert_item(conversation)
        if resp:
            return resp
        else:
            return False

    async def delete_conversation(self, user_id, conversation_id):
        conversation = await self.container_client.read_item(item=conversation_id, partition_key=user_id)        
        if conversation:
            resp = await self.container_client.delete_item(item=conversation_id, partition_key=user_id)
            return resp
        else:
            return True

        
    async def delete_messages(self, conversation_id, user_id):
        ## get a list of all the messages in the conversation
        messages = await self.get_messages(user_id, conversation_id)
        response_list = []
        if messages:
            for message in messages:
                resp = await self.container_client.delete_item(item=message['id'], partition_key=user_id)
                response_list.append(resp)
            return response_list


    async def get_conversations(self, user_id, limit, sort_order = 'DESC', offset = 0):
        parameters = [
            {
                'name': '@userId',
                'value': user_id
            }
        ]
        query = f"SELECT * FROM c where c.userId = @userId and c.type='conversation' order by c.updatedAt {sort_order}"
        if limit is not None:
            query += f" offset {offset} limit {limit}" 
        
        conversations = []
        async for item in self.container_client.query_items(query=query, parameters=parameters):
            conversations.append(item)
        
        return conversations

    async def get_conversation(self, user_id, conversation_id):
        parameters = [
            {
                'name': '@conversationId',
                'value': conversation_id
            },
            {
                'name': '@userId',
                'value': user_id
            }
        ]
        query = f"SELECT * FROM c where c.id = @conversationId and c.type='conversation' and c.userId = @userId"
        conversations = []
        async for item in self.container_client.query_items(query=query, parameters=parameters):
            conversations.append(item)

        ## if no conversations are found, return None
        if len(conversations) == 0:
            return None
        else:
            return conversations[0]
 
    async def create_message(self, uuid, conversation_id, user_id, input_message: dict):
        message = {
            'id': uuid,
            'type': 'message',
            'userId' : user_id,
            'createdAt': datetime.utcnow().isoformat(),
            'updatedAt': datetime.utcnow().isoformat(),
            'conversationId' : conversation_id,
            'role': input_message['role'],
            'content': input_message['content']
        }

        if self.enable_message_feedback:
            message['feedback'] = ''
        
        resp = await self.container_client.upsert_item(message)  
        if resp:
            ## update the parent conversations's updatedAt field with the current message's createdAt datetime value
            conversation = await self.get_conversation(user_id, conversation_id)
            if not conversation:
                return "Conversation not found"
            conversation['updatedAt'] = message['createdAt']
            await self.upsert_conversation(conversation)
            return resp
        else:
            return False
    
    async def update_message_feedback(self, user_id, message_id, feedback):
        message = await self.container_client.read_item(item=message_id, partition_key=user_id)
        if message:
            message['feedback'] = feedback
            resp = await self.container_client.upsert_item(message)
            return resp
        else:
            return False

    async def get_messages(self, user_id, conversation_id):
        parameters = [
            {
                'name': '@conversationId',
                'value': conversation_id
            },
            {
                'name': '@userId',
                'value': user_id
            }
        ]
        query = f"SELECT * FROM c WHERE c.conversationId = @conversationId AND c.type='message' AND c.userId = @userId ORDER BY c.timestamp ASC"
        messages = []
        async for item in self.container_client.query_items(query=query, parameters=parameters):
            messages.append(item)

        return messages


class CosmosLeadGenClient:
    """Handles lead generation data caching in CosmosDB"""
    def __init__(self, cosmosdb_endpoint: str, credential: any, database_name: str, container_name: str):
        self.cosmosdb_endpoint = cosmosdb_endpoint
        self.credential = credential
        self.database_name = database_name
        self.container_name = container_name
        
        try:
            self.cosmosdb_client = CosmosClient(self.cosmosdb_endpoint, credential=self.credential)
            self.database_client = self.cosmosdb_client.get_database_client(database_name)
            self.container_client = self.database_client.get_container_client(container_name)
        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Error initializing Cosmos DB client: {e}")
            raise

    async def get_cached_data(self, url: str):
        """
        Retrieve cached data for the given URL if it's less than 24 hours old.
        """
        query = f"SELECT * FROM c WHERE c.url = @url AND c.timestamp >= @timestamp"
        params = [
            {"name": "@url", "value": url},
            {"name": "@timestamp", "value": (datetime.utcnow() - timedelta(hours=24)).isoformat()},
        ]
        results = []
        async for item in self.container_client.query_items(query=query, parameters=params):
            results.append(item)
        return results[0] if results else None

    async def write_to_cache(self, url: str, data: list, timestamp: str):
        """
        Write new property data to the Cosmos DB cache asynchronously.
        """
        async def upsert_item(record):
            try:
                # Construct the item with metadata
                item = {
                    "id": str(uuid.uuid4()),
                    "url": url,
                    "timestamp": timestamp,
                    **record
                }

                # Log the item being written
                logging.info(f"Attempting to upsert item: {item}")

                # Validate payload
                if not isinstance(record, dict):
                    logging.error(f"Record must be a dictionary. Got: {type(record)}")

                # Upsert the item
                await self.container_client.upsert_item(item)

            except exceptions.CosmosHttpResponseError as e:
                logging.error(f"Failed to write item to Cosmos DB: {e.message}")
                logging.debug(f"Item causing issue: {item}")
                if e.status_code == 400:
                    logging.error("Bad request error: Check the payload structure.")
                elif e.status_code == 413:  # Payload too large
                    logging.error("Item size exceeds the limit of 2 MB.")
                else:
                    logging.error(f"Unexpected error while writing to cache: {e}")

            except Exception as e:
                logging.error(f"Unexpected error while writing to cache: {e}")
                logging.debug(f"Item causing issue: {item}")

        # Create tasks for all records
        tasks = [upsert_item(data)]

        # Run tasks concurrently
        await asyncio.gather(*tasks)

    async def ensure(self):
        """
        Verify the Cosmos DB client, database, and container are initialized correctly.
        """
        try:
            await self.database_client.read()
            await self.container_client.read()
        except exceptions.CosmosResourceNotFoundError as e:
            logging.error(f"Database or container not found: {e}")

class CosmosBuyersClient:
    """Handles buyer retrieval operations in CosmosDB"""
    def __init__(self, cosmosdb_endpoint: str, credential: any, database_name: str, container_name: str):
        self.cosmosdb_endpoint = cosmosdb_endpoint
        self.credential = credential
        self.database_name = database_name
        self.container_name = container_name

        try:
            self.cosmosdb_client = CosmosClient(self.cosmosdb_endpoint, credential=self.credential)
            self.database_client = self.cosmosdb_client.get_database_client(database_name)
            self.container_client = self.database_client.get_container_client(container_name)
        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Error initializing Cosmos DB buyers client: {e}")
            raise

    async def get_buyers_by_city_state(self, city: str, state: str, sample_size: int = 50):       
        # Step 1: Get total count
        count_query = """
            SELECT VALUE COUNT(1) FROM c 
            WHERE CONTAINS(LOWER(c.cities), @city)
            AND c.state = @state
        """
        count_params = [
            {"name": "@city", "value": city.lower().strip()},
            {"name": "@state", "value": state}
        ]
        
        count_items = self.container_client.query_items(
            query=count_query,
            parameters=count_params,
            partition_key=state,  # Add partition key to avoid cross-partition on count
            max_item_count=1,                # 👈 only need one result
            continuation_token_limit=8       # 👈 limit continuation token (KB)
        )
        
        # Iterate through the count result
        total_count = 0
        async for item in count_items:
            total_count = item
            break  # COUNT returns a single value
        
        # Cap the offset to avoid header issues with large offsets
        max_offset = min(500, max(0, total_count - sample_size))
        
        if total_count <= sample_size:
            offset = 0
        else:
            offset = random.randint(0, max_offset)
        
        # Step 2: Query with random offset and ORDER BY
        query = """
            SELECT 
                c["First Name"] AS "First Name",
                c["Last Name"] AS "Last Name",
                c["Full Name"] AS "Full Name",
                c.Phones_Formatted AS Phones,
                c.Email
            FROM c 
            WHERE CONTAINS(LOWER(c.cities), @city) 
            AND c.state = @state 
            ORDER BY c.id
            OFFSET @offset LIMIT @sample_size
        """
        
        parameters = [
            {"name": "@city", "value": city.lower().strip()},
            {"name": "@state", "value": state},
            {"name": "@offset", "value": offset},
            {"name": "@sample_size", "value": sample_size}
        ]
        
        items_iterator = self.container_client.query_items(
            query=query,
            parameters=parameters,
            partition_key=state,  # Add partition key since you're filtering by state
            max_item_count=sample_size,      # 👈 keep pages small-ish
            continuation_token_limit=8 
        )
        
        # Collect all items from the async iterator
        items = []
        async for item in items_iterator:
            items.append(item)
        
        return items
