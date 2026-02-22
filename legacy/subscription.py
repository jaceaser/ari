
# Customer Subscription Management System
from datetime import datetime, timedelta
import json
from typing import Dict, Optional, List
import logging

logger = logging.getLogger("ari")

class SubscriptionManager:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def store_subscription(self, subscription_data: dict, user_email: str):
        """Store subscription data when webhook is received"""
        
        # Extract key info from WooCommerce webhook
        subscription_info = {
            'subscription_id': subscription_data.get('subscription_id'),
            'user_email': user_email,
            'status': subscription_data.get('status', 'active'),
            'plan_type': self._determine_plan_type(subscription_data),
            'created_date': subscription_data.get('date_created', datetime.utcnow().isoformat()),
            'next_payment': subscription_data.get('next_payment_date'),
            'billing_info': subscription_data.get('billing', {}),
            'line_items': subscription_data.get('line_items', []),
            'total': subscription_data.get('total', '0'),
            'currency': subscription_data.get('currency', 'USD'),
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'stripe'
        }
        
        # Store by email for quick lookup
        await self.redis.setex(
            f"subscription:{user_email}",
            86400 * 365,  # Keep for 1 year
            json.dumps(subscription_info)
        )
        
        # Store by subscription ID for webhook updates
        await self.redis.setex(
            f"subscription_id:{subscription_info['subscription_id']}",
            86400 * 365,
            json.dumps(subscription_info)
        )
        
        # Add to active subscriptions list
        await self.redis.sadd("active_subscriptions", user_email)
        
        logger.info(f"Stored subscription {subscription_info['subscription_id']} for {user_email}")
        
        return subscription_info
    
    async def get_subscription(self, user_email: str) -> Optional[Dict]:
        """Get subscription data by email"""
        
        try:
            data = await self.redis.get(f"subscription:{user_email}")
            if data:
                subscription_info = json.loads(data)
                # Check if subscription is still valid
                if subscription_info.get('status') in ['active', 'pending', 'trialing']:
                    return {
                        'has_subscription': True,
                        'subscription_id': subscription_info['subscription_id'],
                        'status': subscription_info['status'],
                        'plan_type': subscription_info['plan_type'],
                        'next_payment': subscription_info.get('next_payment'),
                        'created_date': subscription_info.get('created_date'),
                        'total': subscription_info.get('total')
                    }
            
            return {'has_subscription': False, 'error': 'No active subscription found'}
            
        except Exception as e:
            logger.error(f"Error getting subscription for {user_email}: {e}")
            return {'has_subscription': False, 'error': str(e)}
    
    async def update_subscription_status(self, subscription_id: str, new_status: str):
        """Update subscription status from webhook"""
        
        try:
            # Get existing subscription data
            data = await self.redis.get(f"subscription_id:{subscription_id}")
            if not data:
                logger.warning(f"Subscription {subscription_id} not found for status update")
                return False
            
            subscription_info = json.loads(data)
            user_email = subscription_info['user_email']
            
            # Update status
            subscription_info['status'] = new_status
            subscription_info['last_updated'] = datetime.utcnow().isoformat()
            
            # Store updated data
            updated_data = json.dumps(subscription_info)
            await self.redis.setex(f"subscription:{user_email}", 86400 * 365, updated_data)
            await self.redis.setex(f"subscription_id:{subscription_id}", 86400 * 365, updated_data)
            
            # Update active subscriptions list
            if new_status in ['cancelled', 'expired', 'trash']:
                await self.redis.srem("active_subscriptions", user_email)
                logger.info(f"Removed {user_email} from active subscriptions")
            else:
                await self.redis.sadd("active_subscriptions", user_email)
            
            logger.info(f"Updated subscription {subscription_id} status to {new_status}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating subscription status: {e}")
            return False
    
    async def get_all_active_subscriptions(self) -> List[str]:
        """Get list of all active subscriber emails"""
        try:
            return await self.redis.smembers("active_subscriptions")
        except Exception as e:
            logger.error(f"Error getting active subscriptions: {e}")
            return []
    
    def _determine_plan_type(self, subscription_data: dict) -> str:
        line_items = subscription_data.get('line_items', [])
        for item in line_items:
            # Check explicit tier metadata
            if "tier" in item and item["tier"]:
                return item["tier"]

            product_name = item.get('name', '').lower()
            if 'elite' in product_name:
                return 'ari_elite'
            elif 'pro' in product_name:
                return 'ari_pro'
            elif 'lite' in product_name:
                return 'ari_lite'

        # Fallback to price-based detection
        total = float(subscription_data.get('total', 0))
        if total == 47.0:
            return 'ari_lite'
        elif total == 127.0:
            return 'ari_pro'
        elif total == 197.0:
            return 'ari_elite'

        return 'unknown'
