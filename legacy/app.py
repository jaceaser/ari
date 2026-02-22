import os
import logging
import uuid
import asyncio
import gc 
import aiohttp
import json
import ssl
import secrets
import smtplib
import redis.asyncio as redis
import stripe
from openai import OpenAIError
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from quart_session import Session
from quart import (
    Quart,
    Blueprint,
    jsonify,
    request,
    send_from_directory,
    render_template,
    redirect,
    url_for,
    websocket,
    session,
    make_response,
    current_app
)

from functools import wraps

# Import backend modules
from backend.core.chat_handler import ChatHandler
from backend.services.azure_openai import AzureOpenAIService
from backend.services.cosmos_db import CosmosDBService, CosmosLeadGenClient
from backend.services.lead_gen import LeadGenService
from backend.config.settings import init_app_config
from backend.auth.auth_utils import get_authenticated_user_details
from backend.utils.discorderrorreporter import DiscordErrorReporter

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from backend.services.subscription import SubscriptionManager

# Initialize Blueprint
bp = Blueprint("routes", __name__, static_folder="static", template_folder="static")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# Create logs directory if not exists
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
logger = logging.getLogger("ari")

#-----------------------------INIT REDDIS------------------------------------------#
def create_sync_redis_client(app):
    """Create synchronous Redis client for sessions"""
    host = app.config['REDIS_HOST']
    port = int(app.config['REDIS_PORT'])
    password = app.config['REDIS_PASSWORD']
    
    print(f"Creating SYNC Redis client for sessions: {host}:{port}")
    
    # Use synchronous Redis client for quart-session
    import redis as sync_redis
    
    return sync_redis.Redis(
        host=host,
        port=port,
        password=password,
        ssl=True,
        ssl_cert_reqs=ssl.CERT_NONE,
        ssl_check_hostname=False,
        decode_responses=True,
        socket_timeout=10,
        socket_connect_timeout=10,
        db=0
    )

# Async Redis for sessions
async def create_async_redis_client():
    """Create async Redis client"""
    host = app.config['REDIS_HOST']
    port = int(app.config['REDIS_PORT'])
    password = app.config['REDIS_PASSWORD']
    
    print(f"Creating Redis client with Host: {host}, Port: {port}")
    
    client = redis.Redis(
        host=host,
        port=port,
        password=password,
        ssl=True,
        ssl_cert_reqs=ssl.CERT_NONE,
        ssl_check_hostname=False,
        ssl_ca_certs=None,
        decode_responses=True,
        
        # Connection settings for Azure Redis
        socket_timeout=30,
        socket_connect_timeout=30,
        socket_keepalive=True,
        socket_keepalive_options={},
        
        # Retry settings
        retry_on_timeout=True,
        retry_on_error=[ConnectionError, TimeoutError],
        
        # Pool settings
        max_connections=10,
        
        # Azure Redis specific
        db=0,  # Azure Redis only supports db 0
        username=None,  # Azure Redis uses password auth, not username
    )
    
    return client

#--------------------------------DEFINE REDIS METHODS---------------------------------------#
async def get_redis_client():
    """Get Redis client, creating it if needed"""
    global redis_client
    if redis_client is None:
        redis_client = await create_async_redis_client()
        # Test connection
        await redis_client.ping()
    return redis_client

redis_client = None

async def save_magic_token(token, email, ip_address, skip_ip_validation=False):
    client = await get_redis_client()

    """Save magic token to Redis with optional IP validation skip"""
    token_data = {
        'email': email,
        'expires': (datetime.utcnow() + timedelta(minutes=30)).isoformat(),
        'ip_address': ip_address,
        'used': False,
        'created_at': datetime.utcnow().isoformat(),
        'skip_ip_validation': skip_ip_validation  # Flag for webhook tokens
    }
    
    await client.setex(f"magic_token:{token}", 1800, json.dumps(token_data))
    logger.info(f"Saved magic token {token} to Redis (skip_ip: {skip_ip_validation})")


async def get_magic_token(token):
    client = await get_redis_client()

    """Get magic token from Redis (async)"""
    data = await client.get(f"magic_token:{token}")
    if data:
        token_data = json.loads(data)
        token_data['expires'] = datetime.fromisoformat(token_data['expires'])
        token_data['created_at'] = datetime.fromisoformat(token_data['created_at'])
        return token_data
    return None

async def delete_magic_token(token):
    client = await get_redis_client()

    """Delete magic token from Redis (async) and show remaining tokens"""
    try:
        print(f"🗑️  Deleting token: {token}")
        await client.expire(f"magic_token:{token}", 0)
        logger.info(f"✅ Token {token} deleted")
        
    except Exception as e:
        logger.info(f"❌ Error deleting token {token}: {e}")

async def get_all_magic_tokens():
    """Get all magic tokens from Redis"""
    client = await get_redis_client()
    
    try:
        # Get all keys that match the magic token pattern
        token_keys = await client.keys("magic_token:*")
        
        if not token_keys:
            logger.info("No magic tokens found in Redis")
            return []
        
        # Get all token data
        tokens = []
        for key in token_keys:
            try:
                data = await client.get(key)
                if data:
                    token_data = json.loads(data)
                    # Parse datetime strings
                    token_data['expires'] = datetime.fromisoformat(token_data['expires'])
                    token_data['created_at'] = datetime.fromisoformat(token_data['created_at'])
                    
                    # Add the token ID (extract from key)
                    token_id = key.replace("magic_token:", "")
                    token_data['token_id'] = token_id
                    
                    # Add TTL info
                    ttl = await client.ttl(key)
                    token_data['ttl_seconds'] = ttl
                    
                    tokens.append(token_data)
            except Exception as e:
                logger.info(f"Error processing token {key}: {e}")
        
        logger.info(f"Found {len(tokens)} magic tokens in Redis")
        return tokens
        
    except Exception as e:
        logger.info(f"Error getting magic tokens: {e}")
        return []

async def print_all_magic_tokens():
    """Print all magic tokens in a readable format"""
    tokens = await get_all_magic_tokens()
    
    if not tokens:
        logger.info("No magic tokens found")
        return
    
    logger.info("\n" + "="*80)
    logger.info("MAGIC TOKENS IN REDIS")
    logger.info("="*80)
    
    for i, token in enumerate(tokens, 1):
        logger.info(f"\n{i}. Token ID: {token['token_id']}")
        logger.info(f"   Email: {token['email']}")
        logger.info(f"   IP Address: {token['ip_address']}")
        logger.info(f"   Used: {token['used']}")
        logger.info(f"   Created: {token['created_at']}")
        logger.info(f"   Expires: {token['expires']}")
        logger.info(f"   TTL: {token['ttl_seconds']} seconds")
        
        # Check if expired
        if datetime.utcnow() > token['expires']:
            logger.info(f"   Status: ❌ EXPIRED")
        elif token['used']:
            logger.info(f"   Status: ✅ USED")
        else:
            logger.info(f"   Status: 🟡 ACTIVE")
    
    logger.info("\n" + "="*80)

async def mark_token_as_used(token):
    client = await get_redis_client()

    """Mark token as used in Redis (async)"""
    try:
        data = await client.get(f"magic_token:{token}")
        if data:
            token_data = json.loads(data)
            token_data['used'] = True
            
            ttl = await client.ttl(f"magic_token:{token}")
            if ttl > 0:
                await client.setex(f"magic_token:{token}", ttl, json.dumps(token_data))
                logger.info(f"Marked token {token} as used")
    except Exception as e:
        logger.error(f"Error marking token as used: {e}")

#--------------------------------------CREATE APP WITH REDIS CLIENT----------------------------------#
def create_app():
    global redis_client  # Access the global Redis client
    app = Quart(__name__)

    init_app_config(app)

    sync_client = create_sync_redis_client(app)
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_REDIS'] = sync_client

    @app.before_serving
    async def setup_redis():
        global redis_client
        # Create ONE Redis client and use it for everything
        redis_client = await create_async_redis_client()
        
        # Test the connection
        try:
            await redis_client.ping()
            logger.info("✅ Redis connection successful!")
        except Exception as e:
            logger.info(f"❌ Redis connection failed: {e}")
            raise e
        
        # Set it for sessions too
        app.config['SESSION_REDIS'] = redis_client
    
    @app.after_serving
    async def cleanup_redis():
        global redis_client
        if redis_client:
            await redis_client.aclose()
    
    # Configure Redis sessions
    app.config.update(
        SECRET_KEY=app.config['SECRET_KEY'],
        SESSION_TYPE='redis',
        SESSION_PERMANENT=False,
        SESSION_USE_SIGNER=True,
        SESSION_KEY_PREFIX='reilabs_session:',
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(days=30)
    )
    
    app.register_blueprint(bp)

    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.debug = True
    
    return app



#-------------------------Oauth start----------------------------------------#

# Full path to log file
log_path = os.path.join(log_dir, "execution_logs.log")

logger.setLevel(logging.DEBUG)
logger.propagate = False  # prevent double logging

# Avoid duplicate handlers if re-run
if not logger.handlers:
    handler = RotatingFileHandler(log_path, maxBytes=1000000, backupCount=3)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Example test
logger.info("Logger is working.")


# Exception logger
exp_logger = logging.getLogger("exception_logger")
exp_logger.setLevel(logging.ERROR)
exp_handler = RotatingFileHandler(os.path.join(log_dir, "exception_logs.log"), maxBytes=1_000_000, backupCount=3)
exp_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
exp_logger.addHandler(exp_handler)

exp_logger.info("Exception logger is working...")


# Decorator to check if the user is authenticated
def auth_required(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        user_email = session.get('user_email')
        
        if not user_email:
            logger.warning("WARNING! No user_email in session — redirecting to login")
            return redirect("https://reilabs.ai/login/")
        
        # Check subscription every 24 hours
        auth_time = session.get('auth_time', '')
        should_check = True
        
        if auth_time:
            try:
                last_check = datetime.fromisoformat(auth_time)
                should_check = (datetime.utcnow() - last_check) > timedelta(hours=24)
            except:
                should_check = True
                
        
        if should_check or not session.get('subscription_plan'):
            # Check subscription from Redis (fast)
            subscription_manager = SubscriptionManager(redis_client)
            subscription_info = await subscription_manager.get_subscription(user_email)
            
            if not subscription_info['has_subscription']:
                session.clear()
                error_msg = subscription_info.get('error', 'subscription_expired')
                return redirect(f"https://reilabs.ai/products/?error={error_msg}&email={user_email}")
            
            # Update session with fresh auth time and plan info
            session['auth_time'] = datetime.utcnow().isoformat()
            session['subscription_plan'] = subscription_info.get('plan_type', 'unknown')
            session['subscription_id'] = subscription_info.get('subscription_id')
            session.permanent = True
        
        return await f(*args, **kwargs)
    return decorated_function


# function to force close an unresponsive session to enable seamless streaming and prevent duplicate questions
async def force_cleanup_aiohttp_sessions():
    for obj in gc.get_objects():
        try:
            if isinstance(obj, aiohttp.ClientSession) and not obj.closed:
                logger.warning("Force-closing leaked aiohttp.ClientSession")
                await obj.close()
        except OpenAIError as oe:
            logger.warning(f"Ignored OpenAIError during forced close: {oe}")
            
        except Exception as e:
            logger.error(f"Error while evaluating or closing session: {e}")



'''--------------------------------------- AUTH START ------------------------------------------'''

@bp.route("/")
async def index():
    user_email = session.get('user_email')
    if user_email:
        return redirect(url_for("routes.ari"))
    
    # Redirect to your WordPress login page
    return redirect("https://reilabs.ai/login/")

@bp.route("/login", methods=["POST"])
async def login():
    # Debug IP detection
    x_forwarded = request.headers.get('X-Forwarded-For', 'None')
    remote_addr = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'None')
    
    logger.info(f"LOGIN - X-Forwarded-For: {x_forwarded}")
    logger.info(f"LOGIN - Remote-Addr: {remote_addr}")
    logger.info(f"LOGIN - User-Agent: {user_agent}")
    
    user_ip = get_real_ip(request)
    host_url = app.config['HOST_URL']
    
    logger.info(f"LOGIN - Final IP used: {user_ip}")

    email = (await request.form).get('email')
    if email:
        # ls_service = LemonSqueezyService()
        # subscription_info = await ls_service.check_subscription_status(email)
        # Check subscription from Redis (fast)
        subscription_manager = SubscriptionManager(redis_client)
        subscription_info = await subscription_manager.get_subscription(email)

        if subscription_info['has_subscription']:
            token = secrets.token_urlsafe(32)
            
            await save_magic_token(token, email, user_ip)
            
            # DEBUG: Log token creation
            logger.info(f"CREATED magic link token {token} for {email} from IP {user_ip}")
            
            magic_link = f"{host_url}/auth/verify?token={token}"
            
            await send_magic_link_email(email, magic_link)
            
            return redirect(f"https://reilabs.ai/check-email/?email={email}")
        else:
            return redirect(f"https://reilabs.ai/products/?error=no_subscription&email={email}")
    
    return redirect("https://reilabs.ai/login/?error=missing_email")

@bp.route("/auth/verify")
async def verify_magic_link():
    try:
        # Debug IP detection
        x_forwarded = request.headers.get('X-Forwarded-For', 'None')
        remote_addr = request.remote_addr
        user_agent = request.headers.get('User-Agent', 'None')
        
        logger.info(f"VERIFY - X-Forwarded-For: {x_forwarded}")
        logger.info(f"VERIFY - Remote-Addr: {remote_addr}")
        logger.info(f"VERIFY - User-Agent: {user_agent}")
        
        user_ip = get_real_ip(request)
        logger.info(f"VERIFY - Final IP used: {user_ip}")
        
        token = request.args.get('token')
        logger.info(f"VERIFYING token {token}")
        
        # Get from Redis
        link_data = await get_magic_token(token)
        
        if not link_data:
            logger.warning(f"Token {token} not found in Redis")
            return redirect("https://reilabs.ai/login/?error=invalid_link")
        
        email = link_data['email']
        
        # Security Check 1: Already used?
        if link_data.get('used', False):
            logger.warning(f"Attempt to reuse token for {email}")
            await delete_magic_token(token)  # Delete from Redis
            return redirect("https://reilabs.ai/login/?error=link_already_used")
        
        # Security Check 2: Expired?
        if datetime.utcnow() > link_data['expires']:
            logger.warning(f"Expired token used for {email}")
            await delete_magic_token(token)  # Delete from Redis
            return redirect("https://reilabs.ai/login/?error=link_expired")
        
        # Security Check 3: IP Address Match (only if not webhook token)
        skip_ip_validation = link_data.get('skip_ip_validation', False)
        
        if not skip_ip_validation:
            if link_data.get('ip_address') != user_ip:
                logger.warning(f"IP mismatch for {email}: expected {link_data.get('ip_address')}, got {user_ip}")
                await delete_magic_token(token)
                return redirect("https://reilabs.ai/login/?error=security_violation")
        else:
            logger.info(f"Skipping IP validation for webhook token (user: {email})")
        
        # Mark as used in Redis
        await mark_token_as_used(token)
        
        # Verify subscription is still active
        subscription_manager = SubscriptionManager(redis_client)
        subscription_info = await subscription_manager.get_subscription(email)
        
        if subscription_info['has_subscription']:
            # Log successful login
            logger.info(f"Successful magic link login for {email} from IP {user_ip}")

            # Clear any existing session first
            # session.clear()
            
            # Create session
            session['user_email'] = email
            session['user_name'] = email.split('@')[0].title()
            session['auth_time'] = datetime.utcnow().isoformat()
            session['login_ip'] = user_ip
            session['subscription_plan'] = subscription_info.get('plan_type', 'unknown')
            session['subscription_id'] = subscription_info.get('subscription_id')
            session.permanent = True
            session.modified = True
            
            logger.info(f" Session created for: {email}")
            logger.info(f"Session set - permanent: {session.permanent}")
            logger.info(f"Session data: {dict(session)}")

            
            # Clean up token from Redis
            await delete_magic_token(token)
            
            return redirect(url_for("routes.ari"))
        else:
            # Subscription was cancelled after magic link sent
            logger.warning(f"Subscription no longer active for {email}")
            await delete_magic_token(token)  # Delete from Redis
            return redirect(f"https://reilabs.ai/products/?error=subscription_cancelled&email={email}")
    except Exception as e:
        logger.error(f"Error while performing auth/verify: {e}")
        return redirect("https://reilabs.ai/login/?error=invalid_link")

@bp.route("/api/userinfo")
@auth_required
async def userinfo():
    logger.info(f"Serving user info API for user ID: {session.get('user_name')}")
    return {
        "name": session.get("user_name", "User"),  
        "email": session.get("user_email"),        
        "subscription_plan": session.get("subscription_plan"),
        "subscription_id": session.get("subscription_id")
    }
    

@bp.route("/webhook/stripe", methods=["POST"])
async def stripe_webhook():
    error_context = {
        'location': 'stripe_webhook',
        'timestamp': datetime.now().isoformat()
    }
    try:
        payload = await request.data  # Quart requires await
        sig_header = request.headers.get("Stripe-Signature")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError:
            return "Invalid payload", 400
        except stripe.SignatureVerificationError:
            return "Invalid signature", 400

        subscription_manager = SubscriptionManager(redis_client)

        # ----------------------------
        # Handle Checkout completed
        # ----------------------------
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            customer_email = session.get("customer_details", {}).get("email")
            subscription_id = session.get("subscription")

            if customer_email and subscription_id:
                stripe_sub = stripe.Subscription.retrieve(subscription_id)
                price_obj = stripe_sub["items"]["data"][0]["price"]
                current_period_end = stripe_sub.get("current_period_end")

                subscription_data = {
                    "id": stripe_sub["id"],
                    "status": stripe_sub["status"],
                    "line_items": [
                        {
                            "name": price_obj.get("nickname") or price_obj["id"],
                            "tier": price_obj.get("metadata", {}).get("tier", "unknown")
                        }
                    ],
                    "total": price_obj["unit_amount"] / 100,
                    "currency": price_obj["currency"],
                    "date_created": datetime.utcfromtimestamp(stripe_sub["created"]).isoformat(),
                    "next_payment_date": datetime.utcfromtimestamp(current_period_end).isoformat()
                        if current_period_end else None
                }

                # ✅ Your async logic goes right here
                # -------------------------------------------------
                await subscription_manager.store_subscription(subscription_data, customer_email)

                token = secrets.token_urlsafe(32)
                await save_magic_token(token, customer_email, "webhook", skip_ip_validation=True)

                magic_link = f"https://chat.reilabs.ai/auth/verify?token={token}"
                await send_magic_link_email(customer_email, magic_link)

                logger.info(f"✨ Welcome email sent to {customer_email}")
                # -------------------------------------------------
        # 2️⃣ When Stripe creates the actual subscription object
        elif event["type"] == "customer.subscription.created":
            session = event["data"]["object"]
            subscription_id = session.get("id")
            customer_id = session.get("customer")

            # Retrieve subscription
            stripe_sub = stripe.Subscription.retrieve(subscription_id)

            # Extract price info
            item = stripe_sub["items"]["data"][0]
            price_obj = item["price"]

            # Extract metadata tier
            tier = price_obj.get("metadata", {}).get("tier", "unknown")

            # Extract customer email
            customer = stripe.Customer.retrieve(customer_id)
            customer_email = customer.get("email")

            # Fix: `current_period_end` may not exist yet (even when trialing)
            current_period_end = stripe_sub.get("current_period_end")

            # Build standardized subscription schema
            subscription_data = {
                "id": stripe_sub["id"],
                "status": stripe_sub["status"],
                "plan_type": tier,
                "line_items": [
                    {
                        "name": price_obj.get("nickname") or price_obj["id"],
                        "tier": tier
                    }
                ],
                "total": price_obj["unit_amount"] / 100,
                "currency": price_obj["currency"],
                "date_created": datetime.utcfromtimestamp(
                    stripe_sub["created"]
                ).isoformat(),
                "next_payment_date": (
                    datetime.utcfromtimestamp(current_period_end).isoformat()
                    if current_period_end else None
                )
            }

            # Save to Redis
            await subscription_manager.store_subscription(subscription_data, customer_email)
        # ----------------------------
        # Handle Subscription Updated
        # ----------------------------
        elif event["type"] == "customer.subscription.updated":
            stripe_sub = event["data"]["object"]
            items = (stripe_sub.get("items") or {}).get("data") or []
            item0 = items[0] if items else {}
            current_period_end = stripe_sub.get("current_period_end") or item0.get("current_period_end")
            customer = stripe.Customer.retrieve(stripe_sub["customer"])
            customer_email = customer.get("email")
            price_obj = stripe_sub["items"]["data"][0]["price"]

            if customer_email:
                subscription_data = {
                    "id": stripe_sub["id"],
                    "status": stripe_sub["status"],
                    "line_items": [
                        {
                            "name": price_obj.get("nickname") or price_obj["id"],
                            "tier": price_obj.get("metadata", {}).get("tier", "unknown")
                        }
                    ],
                    "total": price_obj["unit_amount"] / 100,
                    "currency": price_obj["currency"],
                    "date_created": datetime.utcfromtimestamp(stripe_sub["created"]).isoformat(),
                    "next_payment_date": datetime.utcfromtimestamp(
                        current_period_end
                    ).isoformat(),
                }

                subscription_manager.store_subscription(subscription_data, customer_email)

        # ----------------------------
        # Handle Subscription Deleted
        # ----------------------------
        elif event["type"] == "customer.subscription.deleted":
            stripe_sub = event["data"]["object"]
            await subscription_manager.update_subscription_status(stripe_sub["id"], stripe_sub.get("status", "canceled"))

        return jsonify(success=True)
    except Exception as e:
        logger.error("Stripe Webhook Error: %s", e)
        exp_logger.exception(f" Exception caught in /webhook/stripe: {str(e)}")

        error_context.update({
            'location': 'stripe_webhook',
            'timestamp': datetime.now().isoformat()
        })
        await discord_reporter.report_error(e, error_context)
        return jsonify(success=False)

@bp.route("/ari")
@auth_required
async def ari():
    user_name = session.get("user_name", "User")
    return await render_template("index.html", title=app.config['UI_CONFIG']['ui']['title'], 
                               favicon=app.config['UI_CONFIG']['ui']['favicon'], user_name=user_name)

@bp.route("/logout")
async def logout():
    logger.info("User logged out and session cleared")
    session.clear()
    return redirect(url_for("routes.index"))

@bp.route("/debug/session")
async def debug_session():
    return {
        "session": dict(session),
        "email": session.get("user_email"),
        "auth_time": session.get("auth_time"),
    }

     
'''--------------------------------------- AUTH END------------------------------------------'''


@bp.route("/favicon.ico")
async def favicon():
    return await bp.send_static_file("favicon.ico")

@bp.route("/assets/<path:path>")
async def assets(path):
    return await send_from_directory("static/assets", path)

# Chat routes
@bp.route("/conversation", methods=["POST"])
async def conversation():
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    
    discord_reporter = DiscordErrorReporter(
        webhook_url=app.config['DISCORD_WEBHOOK_URL'],
        environment=app.config.get('ENVIRONMENT', 'production')
    )
    
    request_json = await request.get_json()
    cosmos_lead_client = CosmosLeadGenClient(
        cosmosdb_endpoint=f'https://{app.config["COSMOS_DB"]["ACCOUNT"]}.documents.azure.com:443/',
        credential=app.config["COSMOS_DB"]["KEY"],
        database_name=app.config["COSMOS_DB"]["LEADGEN_DATABASE"],
        container_name=app.config["COSMOS_DB"]["LEADGEN_CONTAINER"]
    )

    cosmos_service = CosmosDBService(app.config['COSMOS_DB'])
    openai_service = AzureOpenAIService(app.config['PROMPT_CONFIGS'], discord_reporter, app.config["SEARCH_CONFIG"]["key"], app.config["SEARCH_CONFIG"]["endpoint"])
    lead_gen_service = LeadGenService(
        api_key=app.config["SCRAPING_BEE_API_KEY"],
        exa_api_key=app.config['EXA_API_KEY'],
        cosmos_client=cosmos_lead_client,
        azure_blob_config=app.config["AZURE_BLOB"],
        discord_reporter=discord_reporter
    )

    chat_handler = ChatHandler(
        openai_service=openai_service,
        cosmos_service=cosmos_service,
        lead_gen_service=lead_gen_service,
        prompt_configs=app.config['PROMPT_CONFIGS'],
        discord_reporter=discord_reporter,
        tier=request.cookies.get("subscription")
    )
    
    return chat_handler.handle_conversation(request_json)


#--------------------------------------WEBSOCKET START----------------------------------------#

# socket to handle the live conversation with ARI
@bp.websocket('/ws/conversation')
async def ws_conversation():
    discord_reporter = DiscordErrorReporter(
        webhook_url=app.config['DISCORD_WEBHOOK_URL'],
        environment=app.config.get('ENVIRONMENT', 'production')
    )
    error_context = {
        'location': 'ws_conversation',
        'timestamp': datetime.now().isoformat()
    }
    last_ping = asyncio.get_event_loop().time()
    is_closed = False

    cosmos_lead_client = CosmosLeadGenClient(
        cosmosdb_endpoint=f'https://{app.config["COSMOS_DB"]["ACCOUNT"]}.documents.azure.com:443/',
        credential=app.config["COSMOS_DB"]["KEY"],
        database_name=app.config["COSMOS_DB"]["LEADGEN_DATABASE"],
        container_name=app.config["COSMOS_DB"]["LEADGEN_CONTAINER"]
    )

    cosmos_service = CosmosDBService(app.config['COSMOS_DB'])
    openai_service = AzureOpenAIService(app.config['PROMPT_CONFIGS'], discord_reporter, app.config["SEARCH_CONFIG"]["key"], app.config["SEARCH_CONFIG"]["endpoint"])
    lead_gen_service = LeadGenService(
        api_key=app.config["SCRAPING_BEE_API_KEY"],
        exa_api_key=app.config['EXA_API_KEY'],
        cosmos_client=cosmos_lead_client,
        azure_blob_config=app.config["AZURE_BLOB"],
        discord_reporter=discord_reporter
    )

    chat_handler = ChatHandler(
        openai_service=openai_service,
        cosmos_service=cosmos_service,
        lead_gen_service=lead_gen_service,
        prompt_configs=app.config['PROMPT_CONFIGS'],
        discord_reporter=discord_reporter,
        tier=request.cookies.get("subscription")
    )

    async def check_timeout():
        nonlocal is_closed
        while True:
            await asyncio.sleep(30)
            if is_closed:
                break
            if asyncio.get_event_loop().time() - last_ping > 60:
                logger.warning("Connection timed out.")
                if not is_closed:
                    is_closed = True
                    await websocket.close(code=1001, reason="Connection timeout")
                break

    asyncio.create_task(check_timeout())

    try:
        logger.info("WebSocket connection opened.")
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                last_ping = asyncio.get_event_loop().time()
                await websocket.send_json({"type": "pong"})
            else:
                try:
                    # DEV FIX: Ensure proper cleanup of streaming resources
                    try:
                        async for chunk in chat_handler.handle_conversation(message, stream_override=True):
                            await websocket.send_json(chunk)
                            logger.debug(f"Stream chunk: {chunk}")

                            # # PROD FIX: Disabling the Manual Stream Break and let it naturally stream
                            # if (
                            #         isinstance(chunk, dict)
                            #         and 'choices' in chunk
                            #         and chunk['choices'][0].get('finish_reason') == 'stop'
                            # ):
                            #     break
                    finally:
                        # DEV FIX: Close aiohttp session if needed
                        # if hasattr(openai_service, "close") and callable(openai_service.close):
                        #     await openai_service.close()
                        logger.info("Streaming complete, closing WebSocket")
                    
                    if not is_closed:
                        is_closed = True
                        await websocket.close(code=1000, reason="Streaming complete")
                    break
                except Exception as e:
                    logger.debug(f"Error in conversation_internal: {str(e)}")
                    exp_logger.exception(f" Exception caught in /ws/conversation endpoint \
                                         while generating response: {str(e)}")
                    await discord_reporter.report_error(e, error_context)
                    await websocket.send_json({"error": str(e)})
                    if not is_closed:
                        is_closed = True
                        await websocket.close(code=1011, reason="Internal error")
                    break
    except Exception as e:
        logger.debug(f"WebSocket error: {str(e)}")
        exp_logger.exception(f" Exception caught in /ws/conversation endpoint at the websocket level : {str(e)}")
        error_context.update({
            'location': 'ws_conversation_outer',
            'timestamp': datetime.now().isoformat()
        })
        await discord_reporter.report_error(e, error_context)
        if not is_closed:
            is_closed = True
            await websocket.close(code=1011, reason="Unhandled error")
    finally:
        logger.info("WebSocket connection closed.")
        is_closed = True
        # await force_cleanup_aiohttp_sessions() # call force close 


# socket to handle the chat history 
@bp.websocket('/ws/history/generate')
async def ws_history_generate():
    discord_reporter = DiscordErrorReporter(
        webhook_url=app.config['DISCORD_WEBHOOK_URL'],
        environment=app.config.get('ENVIRONMENT', 'production')
    )
    error_context = {
        'location': 'ws_history_generate',
        'timestamp': datetime.now().isoformat()
    }
    last_ping = asyncio.get_event_loop().time()
    is_closed = False
    TIMEOUT_SECONDS = 300  # 5 minutes timeout

    # Initialize services
    cosmos_lead_client = CosmosLeadGenClient(
        cosmosdb_endpoint=f'https://{app.config["COSMOS_DB"]["ACCOUNT"]}.documents.azure.com:443/',
        credential=app.config["COSMOS_DB"]["KEY"],
        database_name=app.config["COSMOS_DB"]["LEADGEN_DATABASE"],
        container_name=app.config["COSMOS_DB"]["LEADGEN_CONTAINER"]
    )
    cosmos_service = CosmosDBService(app.config['COSMOS_DB'])
    openai_service = AzureOpenAIService(app.config['PROMPT_CONFIGS'], discord_reporter, app.config["SEARCH_CONFIG"].key, app.config["SEARCH_CONFIG"].endpoint, app.config["SEARCH_CONFIG"].semantic_config)
    lead_gen_service = LeadGenService(
        api_key=app.config["SCRAPING_BEE_API_KEY"],
        exa_api_key=app.config['EXA_API_KEY'],
        cosmos_client=cosmos_lead_client,
        azure_blob_config=app.config["AZURE_BLOB"],
        discord_reporter=discord_reporter
    )
    chat_handler = ChatHandler(
        openai_service=openai_service,
        cosmos_service=cosmos_service,
        lead_gen_service=lead_gen_service,
        prompt_configs=app.config['PROMPT_CONFIGS'],
        discord_reporter=discord_reporter,
        tier=session.get("subscription_plan")
    )

    #logger.info("Users Tier", session.get("subscription_plan"))
    async def check_timeout():
        nonlocal is_closed
        while True:
            await asyncio.sleep(30)
            if is_closed:
                break
            
            time_since_ping = asyncio.get_event_loop().time() - last_ping
            logger.debug(f"Time since last activity: {time_since_ping:.1f} seconds")
            
            if time_since_ping > TIMEOUT_SECONDS:
                logger.warning(f"Connection timed out after {time_since_ping:.1f} seconds (limit: {TIMEOUT_SECONDS}s).")
                if not is_closed:
                    is_closed = True
                    await websocket.close(code=1001, reason="Connection timeout")
                break

    asyncio.create_task(check_timeout())

    try:
        logger.info("WebSocket connection opened for history/generate.")
        while True:
            message = await websocket.receive_json()
            
            # Update last_ping for ANY message received (Fix #1)
            last_ping = asyncio.get_event_loop().time()
            logger.debug(f"Received message type: {message.get('type', 'unknown')}")
            
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                logger.debug("Responded to ping with pong")
            else:
                try:
                    # Extract user info
                    user_id = session.get('user_email') # get the current user id from the session object
                    conversation_id = message.get('conversation_id', None)
                    history_metadata = {}

                    error_context.update({
                        'user_id': user_id,
                        'conversation_id': conversation_id,
                        'request_type': 'ws_history_generate'
                    })

                    logger.info(f"Processing message for user: {user_id}, conversation: {conversation_id}")

                    # Create conversation if none exists
                    if not conversation_id:
                        title = await openai_service.generate_title(message["messages"])
                        conversation_dict = await cosmos_service.create_conversation(
                            user_id=user_id,
                            title=title
                        )
                        conversation_id = conversation_dict['id']
                        history_metadata['title'] = title
                        history_metadata['date'] = conversation_dict['createdAt']
                        logger.info(f"Created new conversation: {conversation_id}")

                    history_metadata['conversation_id'] = conversation_id

                    # Save latest user message
                    messages = message["messages"]
                    if len(messages) > 0 and messages[-1]['role'] == "user":
                        created_message = await cosmos_service.create_message(
                            uuid=str(uuid.uuid4()),
                            conversation_id=conversation_id,
                            user_id=user_id,
                            input_message=messages[-1]
                        )
                        if created_message == "Conversation not found":
                            logger.debug(f"Conversation not found: {conversation_id}")
                    else:
                        logger.debug("No user message found in input")

                    #  Prepare and stream request
                    request_body = message
                    request_body['history_metadata'] = history_metadata

                    logger.info("Starting conversation stream")
                    try:
                        async for chunk in chat_handler.handle_conversation(request_body, stream_override=True):
                            await websocket.send_json(chunk)
                    finally:
                        # Ensure aiohttp.ClientSession is properly closed
                        logger.info("Streaming complete, closing WebSocket")

                    if not is_closed:
                        is_closed = True
                        await websocket.close(code=1000, reason="Streaming complete")
                    break

                except Exception as e:
                    
                    logger.error("Error in ws_history_generate: %s", e)
                    exp_logger.exception(f" Exception caught in /ws/history/generate\
                                          while generating response : {str(e)}")

                    await discord_reporter.report_error(e, error_context)
                    await websocket.send_json({"error": str(e)})
                    if not is_closed:
                        is_closed = True
                        await websocket.close(code=1011, reason="Internal error")
                    break

    except Exception as e:
        logger.error("WebSocket outer error in history/generate: %s", e)
        exp_logger.exception(f" Exception caught in /ws/history/generate\
                                          at the websocket level : {str(e)}")

        error_context.update({
            'location': 'ws_history_generate_outer',
            'timestamp': datetime.now().isoformat()
        })
        await discord_reporter.report_error(e, error_context)
        if not is_closed:
            is_closed = True
            await websocket.close(code=1011, reason="Unhandled error")
    finally:
        logger.info("WebSocket connection closed.")
        is_closed = True
        # await force_cleanup_aiohttp_sessions() # force close


#--------------------------------------- WEBSOCKET END --------------------------------------#

# History routes
@bp.route("/history/generate", methods=["POST"])
async def add_conversation():
    user_id = session.get('user_email')

    request_json = await request.get_json()
    conversation_id = request_json.get('conversation_id', None)

    try:
        cosmos_service = CosmosDBService(app.config['COSMOS_DB'])
        openai_service = AzureOpenAIService(app.config['AZURE_OPENAI'])
        history_metadata = {}
        
        if not conversation_id:
            # Use OpenAI service to generate title
            title = await openai_service.generate_title(request_json["messages"])
            conversation_dict = await cosmos_service.create_conversation(user_id=user_id, title=title)
            conversation_id = conversation_dict['id']
            history_metadata['title'] = title
            history_metadata['date'] = conversation_dict['createdAt']
            
        messages = request_json["messages"]
        if len(messages) > 0 and messages[-1]['role'] == "user":
            created_message = await cosmos_service.create_message(
                uuid=str(uuid.uuid4()),
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-1]
            )
            if created_message == "Conversation not found":
                raise Exception(f"Conversation not found for the given conversation ID: {conversation_id}.")
        else:
            raise Exception("No user message found")
        
        request_body = await request.get_json()
        history_metadata['conversation_id'] = conversation_id
        request_body['history_metadata'] = history_metadata
        
        chat_handler = ChatHandler(
            AzureOpenAIService(app.config['AZURE_OPENAI']),
            cosmos_service,
            LeadGenService(app.config['SCRAPING_BEE_API_KEY'], app.config['EXA_API_KEY']),
            tier=request.cookies.get("subscription")
        )
        return await chat_handler.handle_conversation(request_body)
       
    except Exception as e:
        logger.exception("Exception in /history/generate")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/clear", methods=["POST"])
async def clear_messages():
    user_id = session.get('user_email')
    
    request_json = await request.get_json()
    conversation_id = request_json.get('conversation_id', None)

    try:
        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400
        
        cosmos_service = CosmosDBService(app.config['COSMOS_DB'])
        deleted_messages = await cosmos_service.delete_messages(conversation_id, user_id)
        return jsonify({"message": "Successfully deleted messages in conversation", 
                       "conversation_id": conversation_id}), 200
    except Exception as e:
        logger.exception("Exception in /history/clear_messages")
        return jsonify({"error": str(e)}), 500

@bp.route("/history/delete", methods=["DELETE"])
async def delete_conversation():
    user_id = session.get('user_email')
    
    request_json = await request.get_json()
    conversation_id = request_json.get('conversation_id', None)

    try:
        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400
        
        cosmos_service = CosmosDBService(app.config['COSMOS_DB'])
        await cosmos_service.delete_messages(conversation_id, user_id)
        await cosmos_service.delete_conversation(user_id, conversation_id)

        return jsonify({"message": "Successfully deleted conversation and messages", 
                       "conversation_id": conversation_id}), 200
    except Exception as e:
        logger.exception("Exception in /history/delete")
        exp_logger.exception(f" Exception caught in history/delete\
                                          at the conversation/cosmonDB level : {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route("/history/list", methods=["GET"])
async def list_conversations():
    offset = request.args.get("offset", 0)
    user_id = session.get('user_email')

    cosmos_service = CosmosDBService(app.config['COSMOS_DB'])
    conversations = await cosmos_service.get_conversations(user_id, offset=offset, limit=25)
    
    if not isinstance(conversations, list):
        return jsonify({"error": f"No conversations for {user_id} were found"}), 404

    return jsonify(conversations), 200

@bp.route("/history/read", methods=["POST"])
async def get_conversation():
    user_id = session.get('user_email')

    request_json = await request.get_json()
    conversation_id = request_json.get('conversation_id', None)
    
    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400
    
    cosmos_service = CosmosDBService(app.config['COSMOS_DB'])
    conversation = await cosmos_service.get_conversation(user_id, conversation_id)
    
    if not conversation:
        return jsonify({"error": f"Conversation {conversation_id} was not found or access denied."}), 404
    
    conversation_messages = await cosmos_service.get_messages(user_id, conversation_id)
    messages = [{'id': msg['id'], 'role': msg['role'], 'content': msg['content'], 
                'createdAt': msg['createdAt'], 'feedback': msg.get('feedback')} 
               for msg in conversation_messages]

    return jsonify({"conversation_id": conversation_id, "messages": messages}), 200

@bp.route("/history/rename", methods=["POST"])
async def rename_conversation():
    user_id = session.get('user_email')

    request_json = await request.get_json()
    conversation_id = request_json.get('conversation_id', None)
    
    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400
    
    cosmos_service = CosmosDBService(app.config['COSMOS_DB'])
    conversation = await cosmos_service.get_conversation(user_id, conversation_id)
    
    if not conversation:
        return jsonify({"error": f"Conversation {conversation_id} not found or access denied."}), 404

    title = request_json.get("title", None)
    if not title:
        return jsonify({"error": "title is required"}), 400
        
    conversation['title'] = title
    updated_conversation = await cosmos_service.upsert_conversation(conversation)
    return jsonify(updated_conversation), 200

@bp.route("/history/delete_all", methods=["DELETE"])
async def delete_all_conversations():
    user_id = session.get('user_email')

    try:
        cosmos_service = CosmosDBService(app.config['COSMOS_DB'])
        conversations = await cosmos_service.get_conversations(user_id, offset=0, limit=None)
        
        if not conversations:
            return jsonify({"error": f"No conversations for {user_id} were found"}), 404
        
        for conversation in conversations:
            await cosmos_service.delete_messages(conversation['id'], user_id)
            await cosmos_service.delete_conversation(user_id, conversation['id'])
            
        return jsonify({"message": f"Successfully deleted all conversations for user {user_id}"}), 200
    
    except Exception as e:
        logger.exception("Exception in /history/delete_all")
        exp_logger.exception(f" Exception caught in history/delete_all\
                                          at the cosmosDB level : {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route("/history/ensure", methods=["GET"])
async def ensure_cosmos():
    try:
        if not app.config['COSMOS_DB']['ACCOUNT']:
            return jsonify({"error": "CosmosDB is not configured"}), 404
        
        cosmos_service = CosmosDBService(app.config['COSMOS_DB'])
        success, err = await cosmos_service.ensure()
        
        if not success:
            if err:
                return jsonify({"error": err}), 422
            return jsonify({"error": "CosmosDB is not configured or not working"}), 500
        
        return jsonify({"message": "CosmosDB is configured and working"}), 200
        
    except Exception as e:
        logger.exception("Exception in /history/ensure")
        cosmos_exception = str(e)
        
        if "Invalid credentials" in cosmos_exception:
            return jsonify({"error": cosmos_exception}), 401
        elif "Invalid CosmosDB database name" in cosmos_exception:
            return jsonify({"error": f"{cosmos_exception} {app.config['COSMOS_DB']['DATABASE']} for account {app.config['COSMOS_DB']['ACCOUNT']}"}), 422
        elif "Invalid CosmosDB container name" in cosmos_exception:
            return jsonify({"error": f"{cosmos_exception}: {app.config['COSMOS_DB']['CONVERSATIONS_CONTAINER']}"}), 422
        else:
            return jsonify({"error": "CosmosDB is not working"}), 500
            
@bp.route("/history/update", methods=["POST"])
async def update_conversation():
    """Update conversation with assistant's response"""
    try:
        user_id = session.get('user_email')

        request_json = await request.get_json()
        conversation_id = request_json.get('conversation_id', None)

        if not conversation_id:
            return jsonify({"error": "No conversation_id found"}), 400

        cosmos_service = CosmosDBService(app.config['COSMOS_DB'])
        messages = request_json["messages"]

        if len(messages) > 0 and messages[-1]['role'] == "assistant":
            # If there's a tool message before the assistant message
            if len(messages) > 1 and messages[-2].get('role', None) == "tool":
                # Write the tool message first
                await cosmos_service.create_message(
                    uuid=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    user_id=user_id,
                    input_message=messages[-2]
                )

            # Write the assistant message
            await cosmos_service.create_message(
                uuid=messages[-1]['id'],
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-1]
            )

            return jsonify({"success": True}), 200
        else:
            logger.debug("No assistant messages found")
            
            return jsonify({"error": "No assistant messages found"}), 200

    except Exception as e:
        logger.exception("Exception in /history/update")
        exp_logger.exception(f" Exception caught in history/update\
                                          at the conversation level : {str(e)}")
        return jsonify({"error": str(e)}), 500
     
# Frontend settings route
@bp.route("/frontend_settings", methods=["GET"])
def get_frontend_settings():
    try:
        return jsonify(app.config['UI_CONFIG']), 200
    except Exception as e:
        logger.exception("Exception in /frontend_settings")
        return jsonify({"error": str(e)}), 500

async def send_magic_link_email(email, magic_link):
    try:
        # Create multipart message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Your ARI Login Link"
        msg['From'] = app.config['FROM_EMAIL']
        msg['To'] = email
        
                # Plain text version
        text = f'''
        Click to access ARI: {magic_link}
        
        This link expires in 30 minutes for security.
        
        Best regards,
        REI Labs Team
        '''
        
        # HTML version with updated timing
        html = f'''
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: white; color: black;">
            <div style="background: black; padding: 20px; text-align: center;">
                <h1 style="color: rgb(247, 195, 93); margin: 0; font-size: 24px;">REI Labs ARI</h1>
            </div>
            
            <div style="padding: 30px;">
                <h2 style="color: black; margin-top: 0;">Access ARI</h2>
                <p style="color: black;">Click the button below to access ARI:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{magic_link}" 
                       style="background: rgb(247, 195, 93); color: black; padding: 15px 30px; 
                              text-decoration: none; border-radius: 5px; font-weight: bold;
                              display: inline-block; border: 2px solid black;">
                        Access ARI
                    </a>
                </div>
                
                <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px; padding: 15px; margin: 20px 0;">
                    <p style="color: #856404; margin: 0; font-size: 14px;">
                        ⚠️ <strong>Important:</strong> This secure link expires in 30 minutes and can only be used once.
                    </p>
                </div>
                
                <p style="color: #666; font-size: 12px;">
                    If you didn't request this, please ignore this email.
                </p>
            </div>
            
            <div style="background: black; padding: 20px; text-align: center;">
                <p style="color: rgb(247, 195, 93); font-size: 12px; margin: 0;">
                    Best regards,<br>
                    REI Labs Team<br>
                    <a href="https://reilabs.ai" style="color: rgb(247, 195, 93);">reilabs.ai</a>
                </p>
            </div>
        </div>
        '''
        
        # Attach parts
        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))
        
        # Gmail SMTP connection
        try:
            # Create SSL context with proper certificate verification
            context = ssl.create_default_context()
            
            # Try STARTTLS first (port 587)
            server = smtplib.SMTP(app.config['SMTP_SERVER'], 587)
            server.starttls(context=context)
            server.login(app.config['SMTP_USERNAME'], app.config['SMTP_PASSWORD'])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Gmail: Welcome email sent to {email}")
            
        except ssl.SSLError:
            # Fallback: Use SSL directly (port 465)
            logger.warning("STARTTLS failed, trying SSL connection")
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            server = smtplib.SMTP_SSL(app.config['SMTP_SERVER'], 465, context=context)
            server.login(app.config['SMTP_USERNAME'], app.config['SMTP_PASSWORD'])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Gmail SSL: Welcome email sent to {email}")
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"Gmail authentication failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Gmail SMTP error: {e}")
            raise
        
    except Exception as e:
        logger.error(f"SiteGround email failed: {e}")

def get_real_ip(request):
    """Get the real client IP address without port"""
    ip_headers = [
        'X-Forwarded-For',
        'X-Real-IP', 
        'X-Client-IP',
        'CF-Connecting-IP',
        'True-Client-IP'
    ]
    
    for header in ip_headers:
        ip = request.headers.get(header)
        if ip:
            # Take first IP if comma-separated
            ip = ip.split(',')[0].strip()
            # Remove port if present
            if ':' in ip and not ip.startswith('['):  # Not IPv6
                ip = ip.split(':')[0]
            if ip and ip != '127.0.0.1':
                return ip
    
    # Fallback to remote_addr
    return request.remote_addr

# At the end of your app.py
try:
    app = create_app()
    logger.info("Application initialized successfully")
except Exception as e:
    logger.exception(f"Error initializing application: {str(e)}")
    discord_reporter = DiscordErrorReporter(
        webhook_url = app.config['DISCORD_WEBHOOK_URL'],
        environment = app.config.get('ENVIRONMENT', 'production')
    )
    error_context = {  # <-- Move this here, outside of try blocks
        'location': 'create_app',
        'timestamp': datetime.now().isoformat()
    }
    discord_reporter.report_error(e, error_context)
    raise