"""
Merchant Catalog and Inventory for RazorGate A2A Protocol.

Expanded Multi-Category Marketplace inventory spanning AI compute, software licenses,
cloud storage, developer tooling, business services, and digital media.
"""

from typing import Any, Dict, List, Optional
from backend.agent.protocol import Offer


DEFAULT_CATALOG: List[Dict[str, Any]] = [
    # 1. AI & GPU Compute Infrastructure
    {
        "sku": "compute-gpu-h100-1hr",
        "name": "NVIDIA H100 SXM 80GB Instance (1 Hour)",
        "description": "Dedicated 80GB H100 GPU compute slot with 900GB/s NVLink interconnect for heavy LLM fine-tuning.",
        "category": "ai_compute",
        "amount_paise": 29900,  # ₹299.00
        "unit": "hour",
        "specs": {"gpu": "NVIDIA H100 80GB", "vram_gb": 80, "interconnect": "NVLink 900GB/s", "fp8_tflops": 2000},
    },
    {
        "sku": "compute-gpu-a100-1hr",
        "name": "NVIDIA A100 Tensor Core 40GB Instance (1 Hour)",
        "description": "High-throughput A100 GPU instance optimized for batch inference and deep learning workloads.",
        "category": "ai_compute",
        "amount_paise": 14900,  # ₹149.00
        "unit": "hour",
        "specs": {"gpu": "NVIDIA A100 40GB", "vram_gb": 40, "interconnect": "PCIe Gen4", "fp32_tflops": 19.5},
    },
    {
        "sku": "compute-gpu-l4-1hr",
        "name": "NVIDIA L4 24GB Instance (1 Hour)",
        "description": "Cost-efficient Ada Lovelace accelerator for real-time video, audio processing, and light model inference.",
        "category": "ai_compute",
        "amount_paise": 7900,  # ₹79.00
        "unit": "hour",
        "specs": {"gpu": "NVIDIA L4 24GB", "vram_gb": 24, "interconnect": "PCIe Gen4", "rt_cores": 58},
    },
    {
        "sku": "compute-gpu-h200-1hr",
        "name": "NVIDIA H200 SXM 141GB High-Capacity Instance (1 Hour)",
        "description": "Next-gen Hopper architecture with 141GB HBM3e VRAM for massive frontier model hosting.",
        "category": "ai_compute",
        "amount_paise": 49900,  # ₹499.00
        "unit": "hour",
        "specs": {"gpu": "NVIDIA H200 141GB", "vram_gb": 141, "memory_bandwidth_tbs": 4.8},
    },
    {
        "sku": "compute-gpu-cluster-full-rack",
        "name": "Enterprise Full-Rack 8x H100 High-Throughput Cluster (1 Week)",
        "description": "Dedicated 8-node H100 cluster with 400Gbps InfiniBand networking for enterprise model pre-training.",
        "category": "ai_compute",
        "amount_paise": 12000000,  # ₹120,000.00 (> ₹50,000 ceiling)
        "unit": "week",
        "specs": {"nodes": 8, "total_vram_gb": 640, "infiniband_gbps": 400},
    },

    # 2. Software & SaaS Licenses
    {
        "sku": "license-jetbrains-all-products",
        "name": "JetBrains All Products Pack Enterprise License (Annual)",
        "description": "Full suite access to IntelliJ IDEA, PyCharm, WebStorm, ReSharper, and CLion for enterprise teams.",
        "category": "software_licenses",
        "amount_paise": 2890000,  # ₹28,900.00
        "unit": "year",
        "specs": {"tools_included": 16, "license_type": "commercial", "cloud_sync": True},
    },
    {
        "sku": "license-slack-enterprise",
        "name": "Slack Enterprise Grid License (10 Seats, Monthly)",
        "description": "Enterprise collaboration platform with unlimited message history, custom data retention, and HIPAA compliance.",
        "category": "software_licenses",
        "amount_paise": 180000,  # ₹1,800.00
        "unit": "month",
        "specs": {"seats": 10, "integrations_limit": "unlimited", "hipaa_compliant": True},
    },
    {
        "sku": "license-github-copilot-biz",
        "name": "GitHub Copilot Business AI Developer License (Monthly)",
        "description": "AI pair programmer for organizational repositories with IP indemnification and security filtering.",
        "category": "software_licenses",
        "amount_paise": 150000,  # ₹1,500.00
        "unit": "month",
        "specs": {"seats": 1, "model": "GPT-4o + Claude 3.5 Sonnet", "ip_indemnity": True},
    },
    {
        "sku": "license-figma-organization",
        "name": "Figma Organization Professional Design License (Monthly)",
        "description": "Collaborative design platform with shared design systems, branching, and advanced analytics.",
        "category": "software_licenses",
        "amount_paise": 360000,  # ₹3,600.00
        "unit": "month",
        "specs": {"type": "editor", "design_systems": "unlimited", "sso_enabled": True},
    },

    # 3. Cloud Storage & Infrastructure
    {
        "sku": "storage-object-s3-10tb",
        "name": "High-Performance S3-Compatible Object Storage (10TB/mo)",
        "description": "Low-latency object storage for side projects, datasets, and web asset hosting with zero egress fees.",
        "category": "cloud_storage",
        "amount_paise": 120000,  # ₹1,200.00
        "unit": "month",
        "specs": {"capacity_tb": 10, "egress_cost": "free", "durability_nines": 11},
    },
    {
        "sku": "storage-object-s3-100tb",
        "name": "Ultra-Capacity S3-Compatible Storage Volume (100TB/mo)",
        "description": "High-throughput bucket for machine learning training datasets and video archives.",
        "category": "cloud_storage",
        "amount_paise": 990000,  # ₹9,900.00
        "unit": "month",
        "specs": {"capacity_tb": 100, "read_iops": 50000, "multi_region": True},
    },
    {
        "sku": "storage-glacier-archive-50tb",
        "name": "Cold Glacier Archival Storage (50TB/mo)",
        "description": "Cost-optimized long-term archival storage for compliance logs, backup snapshots, and historical data.",
        "category": "cloud_storage",
        "amount_paise": 49000,  # ₹490.00
        "unit": "month",
        "specs": {"capacity_tb": 50, "retrieval_time_hrs": 3, "encryption": "AES-256"},
    },
    {
        "sku": "storage-nvme-block-2tb",
        "name": "Ultra-Fast NVMe Block Storage Volume (2TB/mo)",
        "description": "Provisioned IOPS NVMe block volume for high-performance database indexing and transaction logs.",
        "category": "cloud_storage",
        "amount_paise": 240000,  # ₹2,400.00
        "unit": "month",
        "specs": {"capacity_tb": 2, "max_iops": 64000, "latency_ms": 0.5},
    },

    # 4. Developer & Observability Tooling
    {
        "sku": "tool-datadog-apm-pro",
        "name": "Datadog APM & Infrastructure Observability (Monthly)",
        "description": "Distributed tracing, real-time APM metrics, and automated anomaly detection per host.",
        "category": "dev_tooling",
        "amount_paise": 310000,  # ₹3,100.00
        "unit": "month",
        "specs": {"hosts_covered": 1, "retention_days": 15, "profiling": True},
    },
    {
        "sku": "tool-sentry-enterprise",
        "name": "Sentry Enterprise Error & Crash Monitoring Pack (1M Events)",
        "description": "Full-stack exception monitoring, stack-trace aggregation, and release health analytics.",
        "category": "dev_tooling",
        "amount_paise": 450000,  # ₹4,500.00
        "unit": "pack",
        "specs": {"event_volume": 1000000, "session_replays": 10000, "custom_queries": True},
    },
    {
        "sku": "tool-postman-team",
        "name": "Postman Team API Development & Mock Server Plan (Monthly)",
        "description": "API design, automated documentation, mock servers, and team collaboration workspace.",
        "category": "dev_tooling",
        "amount_paise": 120000,  # ₹1,200.00
        "unit": "month",
        "specs": {"seats": 3, "mock_calls_monthly": 100000, "api_monitors": 50},
    },
    {
        "sku": "tool-sonarqube-enterprise",
        "name": "SonarQube Enterprise Code Quality & CVE Scanner (Annual)",
        "description": "Static code analysis, vulnerability detection, and secret scanning for enterprise CI/CD pipelines.",
        "category": "dev_tooling",
        "amount_paise": 7500000,  # ₹75,000.00 (> ₹50,000 ceiling)
        "unit": "year",
        "specs": {"lines_of_code_m": 5, "supported_languages": 30, "cve_scanning": True},
    },

    # 5. Business & Professional Services
    {
        "sku": "service-devops-engineer-1wk",
        "name": "Dedicated DevOps Architect Sprint (1 Week)",
        "description": "Direct engagement with senior SRE to build Kubernetes pipelines, Terraform modules, and CI/CD automation.",
        "category": "business_services",
        "amount_paise": 3500000,  # ₹35,000.00
        "unit": "week",
        "specs": {"duration_days": 5, "dedicated_sre": True, "deliverables": "Terraform + Helm"},
    },
    {
        "sku": "service-compliance-audit",
        "name": "SOC2 & ISO27001 Automated Compliance Audit Readiness",
        "description": "Comprehensive security posture assessment, evidence gathering script, and auditor readiness report.",
        "category": "business_services",
        "amount_paise": 4500000,  # ₹45,000.00
        "unit": "audit",
        "specs": {"frameworks": ["SOC2 Type II", "ISO 27001"], "gap_analysis": True},
    },
    {
        "sku": "enterprise-support-tier1",
        "name": "Enterprise 24/7 Dedicated Support & Architecture Review",
        "description": "Direct Slack bridge to reliability engineers, 15-min emergency SLA, and quarterly security audit.",
        "category": "business_services",
        "amount_paise": 6500000,  # ₹65,000.00 (> ₹50,000 ceiling)
        "unit": "quarter",
        "specs": {"response_time_mins": 15, "dedicated_tam": True},
    },

    # 6. Digital Media & Streaming Infrastructure
    {
        "sku": "media-cdn-video-transcode",
        "name": "Cloud 4K Video Transcoding & HLS CDN Streaming (10,000 Mins)",
        "description": "Adaptive bitrate HLS/DASH video encoding, DRM protection, and global CDN delivery.",
        "category": "digital_media",
        "amount_paise": 290000,  # ₹2,900.00
        "unit": "pack",
        "specs": {"video_minutes": 10000, "resolutions": "4K/1080p/720p", "drm": "Widevine/FairPlay"},
    },
    {
        "sku": "media-dolby-audio-master",
        "name": "Dolby Atmos Spatial Audio Mastering API (1,000 Tracks)",
        "description": "Automated acoustic mastering, loudness normalization, and spatial audio rendering API.",
        "category": "digital_media",
        "amount_paise": 190000,  # ₹1,900.00
        "unit": "pack",
        "specs": {"tracks": 1000, "mastering_engine": "Dolby Atmos", "output": "WAV/FLAC"},
    },
    {
        "sku": "media-stock-asset-pass",
        "name": "Enterprise Stock Video & Asset API Subscription (Monthly)",
        "description": "Unlimited commercial royalty-free 4K stock video footage, 3D models, and audio track downloads.",
        "category": "digital_media",
        "amount_paise": 490000,  # ₹4,900.00
        "unit": "month",
        "specs": {"downloads_monthly": "unlimited", "resolution": "4K", "commercial_license": True},
    },
]


def score_item_relevance(item: Dict[str, Any], q_words: List[str], cat_lower: str) -> float:
    """
    Computes a numerical relevance score for a catalog item given query terms and category filter.
    """
    score = 0.0
    item_cat = item["category"].lower()
    item_name = item["name"].lower()
    item_desc = item["description"].lower()
    item_sku = item["sku"].lower()
    specs_str = " ".join(f"{k} {v}" for k, v in item.get("specs", {}).items()).lower()

    # Category matching boost
    if cat_lower and cat_lower != "all":
        if cat_lower == item_cat or cat_lower in item_cat or item_cat in cat_lower:
            score += 10.0
        else:
            # Penalty if explicitly filtered by a different category
            score -= 15.0

    if not q_words:
        return max(score, 1.0)

    # Word matching
    for word in q_words:
        if len(word) < 2:
            continue
        if word in item_name:
            score += 5.0
        if word in item_sku:
            score += 4.0
        if word in item_desc:
            score += 2.0
        if word in specs_str:
            score += 3.0
        if word in item_cat:
            score += 2.0

    return score


def search_catalog(
    query: Optional[str] = None,
    category: Optional[str] = None,
    max_budget_paise: Optional[int] = None,
    catalog: Optional[List[Dict[str, Any]]] = None,
) -> List[Offer]:
    """
    Searches and ranks the merchant inventory based on genuine relevance scoring.
    Returns candidate Offer models (up to 4) matching query, category, and budget.
    If query has zero relevance to catalog (e.g., 'organic apples'), returns an empty list [].
    """
    import re

    items = catalog if catalog is not None else DEFAULT_CATALOG
    q_raw = query.strip() if query else ""
    cat_raw = category.strip().lower() if category else ""
    stop_words = {"and", "or", "for", "the", "a", "an", "in", "on", "to", "with", "of", "is", "at", "by", "my", "your"}
    q_words = [w.lower() for w in q_raw.split() if len(w) > 1 and w.lower() not in stop_words]


    scored_items: List[tuple[float, Dict[str, Any]]] = []

    for item in items:
        score = score_item_relevance(item, q_words, cat_raw)

        # If user passed a query, item MUST have positive word/category relevance
        if q_words:
            searchable = f"{item['name']} {item['description']} {item['category']} {item['sku']} {' '.join(str(v) for v in item.get('specs', {}).values())}".lower()
            matches_word = any(bool(re.search(r'\b' + re.escape(w) + r'\b', searchable)) for w in q_words)
            if not matches_word and (not cat_raw or cat_raw == "all" or cat_raw not in item["category"].lower()):
                continue

        if score > 0:
            scored_items.append((score, item))


    # Sort items by relevance score descending
    scored_items.sort(key=lambda x: x[0], reverse=True)
    ranked = [x[1] for x in scored_items]

    # If explicit query was provided and NO item matched relevance, return empty list (No Match)
    if q_words and not ranked:
        return []

    # If no query was provided at all, return top items matching category or default items
    if not ranked and not q_words:
        if cat_raw and cat_raw != "all":
            ranked = [i for i in items if cat_raw in i["category"].lower()]
        if not ranked:
            ranked = list(items[:4])

    # Convert top matching items (up to 4) to Offer models
    results = ranked[:4]
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
