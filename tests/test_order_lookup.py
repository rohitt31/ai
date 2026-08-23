"""
Unit tests for the order lookup tool.
These tests run without an API key and verify deterministic behavior.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.tools.order_lookup import (
    normalize_order_id,
    sanitize_order,
    lookup_order,
)


class TestNormalizeOrderId:
    """Test order ID normalization."""
    
    def test_uppercase(self):
        assert normalize_order_id("ord-1001") == "ORD-1001"
    
    def test_whitespace(self):
        assert normalize_order_id("  ORD-1001  ") == "ORD-1001"
    
    def test_lowercase_with_whitespace(self):
        assert normalize_order_id(" ord-1002 ") == "ORD-1002"
    
    def test_number_only(self):
        assert normalize_order_id("1001") == "ORD-1001"
    
    def test_invalid_format(self):
        assert normalize_order_id("abc-xyz") == ""
    
    def test_empty_string(self):
        assert normalize_order_id("") == ""
    
    def test_special_characters(self):
        assert normalize_order_id("ORD-1001!") == ""


class TestSanitizeOrder:
    """Test that internal fields are properly stripped."""
    
    def test_removes_email(self):
        order = {"order_id": "ORD-1001", "customer_email": "test@test.com", "status": "shipped"}
        sanitized = sanitize_order(order, "shipped")
        assert "customer_email" not in sanitized
    
    def test_removes_address(self):
        order = {"order_id": "ORD-1001", "shipping_address": "123 Main St", "status": "shipped"}
        sanitized = sanitize_order(order, "shipped")
        assert "shipping_address" not in sanitized
    
    def test_removes_internal_notes(self):
        order = {"order_id": "ORD-1001", "internal_notes": "VIP customer", "status": "shipped"}
        sanitized = sanitize_order(order, "shipped")
        assert "internal_notes" not in sanitized
    
    def test_removes_risk_score(self):
        order = {"order_id": "ORD-1001", "risk_score": 0.95, "status": "shipped"}
        sanitized = sanitize_order(order, "shipped")
        assert "risk_score" not in sanitized
    
    def test_removes_sku_from_items(self):
        order = {
            "order_id": "ORD-1001",
            "items": [{"name": "Tumbler", "sku": "BRZ-001", "quantity": 1}],
            "status": "shipped",
        }
        sanitized = sanitize_order(order, "shipped")
        assert "sku" not in sanitized["items"][0]
        assert sanitized["items"][0]["name"] == "Tumbler"
    
    def test_cancelled_hides_delivery_fields(self):
        order = {
            "order_id": "ORD-1004",
            "status": "cancelled",
            "estimated_delivery": "2026-06-27",
            "tracking_number": "1Z999",
        }
        sanitized = sanitize_order(order, "cancelled")
        assert "estimated_delivery" not in sanitized
        assert "tracking_number" not in sanitized
    
    def test_returned_hides_estimated_delivery(self):
        order = {
            "order_id": "ORD-1008",
            "status": "returned",
            "estimated_delivery": "2026-05-17",
            "refund_status": "completed",
        }
        sanitized = sanitize_order(order, "returned")
        assert "estimated_delivery" not in sanitized
        assert sanitized["refund_status"] == "completed"
    
    def test_shipped_preserves_delivery_fields(self):
        order = {
            "order_id": "ORD-1002",
            "status": "shipped",
            "estimated_delivery": "2026-08-05",
            "tracking_number": "1Z999BB",
        }
        sanitized = sanitize_order(order, "shipped")
        assert sanitized["estimated_delivery"] == "2026-08-05"
        assert sanitized["tracking_number"] == "1Z999BB"


class TestLookupOrder:
    """Test the full order lookup function."""
    
    def test_valid_order(self):
        result = lookup_order("ORD-1001")
        assert result["success"] is True
        assert result["order"]["order_id"] == "ORD-1001"
        assert "customer_email" not in result["order"]
    
    def test_case_insensitive(self):
        result = lookup_order("ord-1001")
        assert result["success"] is True
    
    def test_unknown_order(self):
        result = lookup_order("ORD-9999")
        assert result["success"] is False
        assert "not found" in result["error"].lower() or "no order" in result["error"].lower()
    
    def test_invalid_format(self):
        result = lookup_order("invalid")
        assert result["success"] is False
        assert "invalid" in result["error"].lower() or "format" in result["error"].lower()
    
    def test_cancelled_order_no_delivery(self):
        result = lookup_order("ORD-1004")
        assert result["success"] is True
        assert result["order"]["status"] == "cancelled"
        assert "estimated_delivery" not in result["order"]
    
    def test_returned_order_has_refund_info(self):
        result = lookup_order("ORD-1008")
        assert result["success"] is True
        assert result["order"]["status"] == "returned"
        assert "refund_status" in result["order"]
    
    def test_no_internal_notes_exposed(self):
        result = lookup_order("ORD-1008")
        assert result["success"] is True
        assert "internal_notes" not in result["order"]
        # Check the entire serialized output doesn't contain internal note content
        import json
        output = json.dumps(result)
        assert "warehouse error" not in output.lower()
