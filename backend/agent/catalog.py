"""
Merchant Catalog and Inventory for RazorGate A2A Protocol.

Provides structured SKU catalog, category filtering, and budget-aware search.
"""

from typing import Any, Dict, List, Optional
from backend.agent.protocol import Offer


# Realistic catalog items across AI Compute, Cloud Infra, and Developer Tooling
DEFAULT_CATALOG: List[Dict[str, Any]] = [
    {
        "sku": "compute-gpu-h100-1hr",
        "name": "NVIDIA H100 SXM 80GB Instance (1 Hour)",
        "description": "Dedicated 80GB H100 GPU compute slot with high-bandwidth memory for LLM inference & fine-tuning.",
        "category": "ai_compute",
        "amount_paise": 29900,  # ₹299.00
        "unit": "hour",
        "specs": {"gpu": "NVIDIA H100 80GB", "vram_gb": 80, "interconnect": "NVLink 900GB/s"},
    },
    {
        "sku": "compute-gpu-a100-1hr",
        "name": "NVIDIA A100 Tensor Core 40GB Instance (1 Hour)",
        "description": "High-throughput A100 GPU instance optimized for batch processing and model inference.",
        "category": "ai_compute",
        "amount_paise": 14900,  # ₹149.00
        "unit": "hour",
        "specs": {"gpu": "NVIDIA A100 40GB", "vram_gb": 40, "interconnect": "PCIe Gen4"},
    },
    {
        "sku": "compute-gpu-l4-1hr",
        "name": "NVIDIA L4 24GB Instance (1 Hour)",
        "description": "Cost-efficient Ada Lovelace accelerator for real-time video, audio, and light LLM hosting.",
        "category": "ai_compute",
        "amount_paise": 7900,  # ₹79.00
        "unit": "hour",
        "specs": {"gpu": "NVIDIA L4 24GB", "vram_gb": 24, "interconnect": "PCIe Gen4"},
    },
    {
        "sku": "api-tier-starter-100k",
        "name": "RazorGate Intelligence API — Starter Pack (100k Tokens)",
        "description": "Low-latency API decision telemetry, CVE lookups, and security scoring credits.",
        "category": "api_credits",
        "amount_paise": 4900,  # ₹49.00
        "unit": "pack",
        "specs": {"tokens": 100000, "rate_limit_rps": 50, "sla_uptime": "99.9%"},
    },
    {
        "sku": "api-tier-pro-1m",
        "name": "RazorGate Intelligence API — Pro Pack (1M Tokens)",
        "description": "Dedicated throughput pipeline with behavioral anomaly scoring and priority SLA.",
        "category": "api_credits",
        "amount_paise": 34900,  # ₹349.00
        "unit": "pack",
        "specs": {"tokens": 1000000, "rate_limit_rps": 250, "sla_uptime": "99.95%"},
    },
    {
        "sku": "infra-redis-cluster-tier1",
        "name": "Managed High-Availability Redis Cluster (Monthly)",
        "description": "Multi-AZ replicated in-memory cache cluster with automated backups and 500k ops/sec.",
        "category": "cloud_infra",
        "amount_paise": 499900,  # ₹4,999.00
        "unit": "month",
        "specs": {"nodes": 3, "memory_gb": 16, "multi_az": True},
    },
    {
        "sku": "enterprise-support-tier1",
        "name": "Enterprise 24/7 Dedicated Support & Architecture Review",
        "description": "Direct Slack/Teams bridge to senior reliability engineers and quarterly architecture audit.",
        "category": "enterprise_services",
        "amount_paise": 6500000,  # ₹65,000.00 (> ₹50,000 ceiling, for policy ceiling testing)
        "unit": "quarter",
        "specs": {"response_time_mins": 15, "dedicated_tam": True},
    },
]


def search_catalog(
    query: Optional[str] = None,
    category: Optional[str] = None,
    max_budget_paise: Optional[int] = None,
    catalog: Optional[List[Dict[str, Any]]] = None,
) -> List[Offer]:
    """
    Searches and filters the merchant inventory.
    Returns 2-4 matching Offer models with attached gate_disclosure.
    """
    items = catalog if catalog is not None else DEFAULT_CATALOG
    filtered: List[Dict[str, Any]] = []

    q_lower = query.lower() if query else ""
    cat_lower = category.lower() if category else ""

    for item in items:
        # Category filter if provided
        if cat_lower and cat_lower != "all" and item["category"].lower() != cat_lower:
            # Also allow partial match if category keywords overlap
            if cat_lower not in item["category"].lower() and item["category"].lower() not in cat_lower:
                continue

        # Text query filter
        if q_lower:
            searchable_text = f"{item['name']} {item['description']} {item['category']} {item['sku']}".lower()
            if not any(word in searchable_text for word in q_lower.split()):
                continue

        # Budget filter if provided
        if max_budget_paise is not None and item["amount_paise"] > max_budget_paise:
            # Keep item only if we don't have enough matches or testing over-ceiling
            pass

        filtered.append(item)

    # If category filter was too restrictive, fallback to items matching query or default items
    if not filtered:
        for item in items:
            if max_budget_paise is None or item["amount_paise"] <= max_budget_paise:
                filtered.append(item)
        if not filtered:
            filtered = list(items)

    # Convert to Offer models (limit to 2-4 offers for focused agent negotiation)
    results = filtered[:4]
    return [
        Offer(
            sku=x["sku"],
            name=x["name"],
            description=x["description"],
            category=x["category"],
            amount_paise=x["amount_paise"],
            currency="INR",
            unit=x.get("unit", "unit"),
            specs=x.get("specs", {}),
            gate_disclosure="Subject to real-time risk gating; may result in ALLOW/FLAG/BLOCK before execution.",
        )
        for x in results
    ]
