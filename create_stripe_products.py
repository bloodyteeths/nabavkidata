#!/usr/bin/env python3
"""Create Stripe products and prices for nabavkidata in live mode"""

import stripe
import os
from dotenv import load_dotenv

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

products_config = [
    {
        "name": "Nabavkidata Free",
        "description": "Free tier - 3 AI queries per day, basic search",
        "tier": "free",
        "monthly_mkd": 0,
        "yearly_mkd": 0,
    },
    {
        "name": "Nabavkidata Starter",
        "description": "Starter tier - 5 AI queries per day, advanced filters, CSV/PDF export",
        "tier": "starter",
        "monthly_mkd": 89900,  # 899.00 MKD (in stotinki)
        "yearly_mkd": 899000,  # 8990.00 MKD
    },
    {
        "name": "Nabavkidata Professional",
        "description": "Professional tier - 20 AI queries per day, analytics, integrations",
        "tier": "professional",
        "monthly_mkd": 239900,  # 2399.00 MKD
        "yearly_mkd": 2399000,  # 23990.00 MKD
    },
    {
        "name": "Nabavkidata Enterprise",
        "description": "Enterprise tier - Unlimited queries, white-label, API access, 24/7 support",
        "tier": "enterprise",
        "monthly_mkd": 599900,  # 5999.00 MKD
        "yearly_mkd": 5999000,  # 59990.00 MKD
    },
]

results = {}

for config in products_config:
    tier = config["tier"]
    name = config["name"]
    print(f"Creating product: {name}")

    product = stripe.Product.create(
        name=name,
        description=config["description"],
        metadata={"tier": tier, "app": "nabavkidata"}
    )
    print(f"  Product ID: {product.id}")
    results[tier] = {"product_id": product.id}

    if config["monthly_mkd"] > 0:
        monthly_price = stripe.Price.create(
            product=product.id,
            unit_amount=config["monthly_mkd"],
            currency="mkd",
            recurring={"interval": "month"},
            nickname=f"{name} Monthly",
            metadata={"tier": tier, "interval": "monthly"}
        )
        print(f"  Monthly: {monthly_price.id} ({config['monthly_mkd']/100} MKD/month)")
        results[tier]["monthly"] = monthly_price.id

        yearly_price = stripe.Price.create(
            product=product.id,
            unit_amount=config["yearly_mkd"],
            currency="mkd",
            recurring={"interval": "year"},
            nickname=f"{name} Yearly",
            metadata={"tier": tier, "interval": "yearly"}
        )
        print(f"  Yearly: {yearly_price.id} ({config['yearly_mkd']/100} MKD/year)")
        results[tier]["yearly"] = yearly_price.id

print("\n=== ENV VALUES ===")
for tier, data in results.items():
    tier_upper = tier.upper()
    print(f"STRIPE_{tier_upper}_PRODUCT={data['product_id']}")
    if "monthly" in data:
        print(f"STRIPE_{tier_upper}_MONTHLY={data['monthly']}")
    if "yearly" in data:
        print(f"STRIPE_{tier_upper}_YEARLY={data['yearly']}")
