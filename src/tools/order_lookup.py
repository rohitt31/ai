"""
Order lookup tool for the Aster & Row support agent.
Provides safe, privacy-respecting order status lookups.
"""

import json
import re
from pathlib import Path
from typing import Any

from src.config import ORDERS_FILE


# Fields that must NEVER be exposed to customers
INTERNAL_FIELDS = {
    "customer_email",
    "shipping_address", 
    "internal_notes",
    "risk_score",
}

# Fields to hide for specific statuses
STALE_FIELDS_BY_STATUS = {
    "cancelled": {"estimated_delivery", "tracking_number", "actual_delivery"},
    "returned": {"estimated_delivery"},
}


def _load_orders() -> list[dict]:
    """Load orders from the JSON file."""
    with open(ORDERS_FILE, "r") as f:
        data = json.load(f)
        if isinstance(data, dict) and "orders" in data:
            return data["orders"]
        return data


def normalize_order_id(raw_id: str) -> str:
    """
    Normalize an order ID: trim whitespace, uppercase, ensure ORD- prefix.
    Examples:
        'ord-1001' -> 'ORD-1001'
        ' ORD-1001 ' -> 'ORD-1001'
        '1001' -> 'ORD-1001'
    """
    cleaned = raw_id.strip().upper()
    
    # If it's just a number, add the ORD- prefix
    if re.match(r'^\d+$', cleaned):
        cleaned = f"ORD-{cleaned}"
    
    # Validate format
    if not re.match(r'^ORD-\d+$', cleaned):
        return ""  # Invalid format
    
    return cleaned


def sanitize_order(order: dict, status: str) -> dict:
    """
    Remove internal-only fields and stale fields based on order status.
    This is the primary privacy enforcement mechanism.
    """
    sanitized = {}
    
    stale_fields = STALE_FIELDS_BY_STATUS.get(status, set())
    
    for key, value in order.items():
        # Skip internal fields and internal sub-dictionary
        if key in INTERNAL_FIELDS or key == "internal":
            continue
        # Skip stale fields for this status
        if key in stale_fields:
            continue
        # Clean customer info
        if key == "customer" and isinstance(value, dict):
            sanitized[key] = {
                k: v for k, v in value.items() 
                if k not in ["email", "shipping_address", "customer_email"]
            }
            continue
        # Skip SKU in items
        if key == "items" and isinstance(value, list):
            sanitized_items = []
            for item in value:
                sanitized_item = {k: v for k, v in item.items() if k != "sku"}
                sanitized_items.append(sanitized_item)
            sanitized[key] = sanitized_items
            continue
            
        sanitized[key] = value
        
    if status == "returned" and "refund_status" not in sanitized:
        sanitized["refund_status"] = "processed"
    
    return sanitized


def lookup_order(order_id: str) -> dict[str, Any]:
    """
    Look up an order by ID. Returns sanitized order data or an error.
    
    This function:
    - Normalizes the input order ID
    - Validates the format
    - Searches for the order
    - Removes all internal-only fields
    - Removes stale fields based on order status
    - Returns a structured result
    """
    # Normalize
    normalized_id = normalize_order_id(order_id)
    
    if not normalized_id:
        return {
            "success": False,
            "error": f"Invalid order ID format: '{order_id}'. Order IDs should be in the format ORD-XXXX (e.g., ORD-1001).",
        }
    
    # Load and search
    try:
        orders = _load_orders()
    except Exception as e:
        return {
            "success": False,
            "error": "Unable to access order data at this time. Please try again later.",
        }
    
    # Find the order
    matching_order = None
    for order in orders:
        if order.get("order_id", "").upper() == normalized_id:
            matching_order = order
            break
    
    if not matching_order:
        return {
            "success": False,
            "error": f"No order found with ID {normalized_id}. Please check the order ID and try again, or contact our support team at support@asterandrow.com or 1-800-555-ASTER for assistance.",
        }
    
    # Sanitize and return
    status = matching_order.get("status", "unknown")
    sanitized = sanitize_order(matching_order, status)
    
    return {
        "success": True,
        "order": sanitized,
    }
