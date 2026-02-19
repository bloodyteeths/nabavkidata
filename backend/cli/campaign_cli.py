#!/usr/bin/env python3
"""
Campaign CLI
Command-line interface for managing report-first outreach campaigns

Usage:
    python -m backend.cli.campaign_cli create --name "My Campaign"
    python -m backend.cli.campaign_cli select-targets <campaign_id> --limit 100
    python -m backend.cli.campaign_cli generate-reports <campaign_id>
    python -m backend.cli.campaign_cli activate <campaign_id>
    python -m backend.cli.campaign_cli send <campaign_id> --batch-size 10
    python -m backend.cli.campaign_cli status <campaign_id>
"""
import os
import sys
import json
import asyncio
import argparse
from datetime import datetime
import uuid
from dotenv import load_dotenv
load_dotenv()


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncpg

# Database configuration
DB_HOST = os.getenv("DB_HOST", "nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "nabavkidata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


async def get_pool():
    """Create database connection pool"""
    return await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        min_size=2,
        max_size=10
    )


async def cmd_create(args):
    """Create a new campaign"""
    from backend.services.campaign_sender import DEFAULT_SETTINGS

    pool = await get_pool()

    settings = {
        **DEFAULT_SETTINGS,
        "min_participations": args.min_participations,
        "min_wins": args.min_wins,
        "lookback_days": args.lookback_days,
        "missed_tenders_days": args.missed_days,
        "attach_pdf_first_n": args.attach_pdf,
        "daily_limit": args.daily_limit,
        "hourly_limit": args.hourly_limit
    }

    campaign_id = uuid.uuid4()

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO report_campaigns (id, name, description, settings, status)
            VALUES ($1, $2, $3, $4, 'draft')
        """, campaign_id, args.name, args.description, json.dumps(settings))

    print(f"\nКампања креирана успешно!")
    print(f"ID: {campaign_id}")
    print(f"Име: {args.name}")
    print(f"Статус: draft")
    print(f"\nСледен чекор: python -m backend.cli.campaign_cli select-targets {campaign_id}")

    await pool.close()


async def cmd_select_targets(args):
    """Select top companies as campaign targets"""
    from backend.services.email_enrichment import select_top_companies, enrich_missing_emails

    pool = await get_pool()

    # Get campaign
    async with pool.acquire() as conn:
        campaign = await conn.fetchrow("""
            SELECT settings FROM report_campaigns WHERE id = $1
        """, uuid.UUID(args.campaign_id))

        if not campaign:
            print(f"Кампања {args.campaign_id} не е пронајдена")
            return

        settings = json.loads(campaign['settings']) if campaign['settings'] else {}

    print(f"\nСелектирање топ компании за кампања {args.campaign_id}...")
    print(f"Минимум учества: {settings.get('min_participations', 5)}")
    print(f"Минимум победи: {settings.get('min_wins', 2)}")

    # Select companies
    companies = await select_top_companies(
        pool=pool,
        min_participations=settings.get("min_participations", 5),
        min_wins=settings.get("min_wins", 2),
        lookback_days=settings.get("lookback_days", 365),
        limit=args.limit
    )

    print(f"Пронајдени {len(companies)} компании")

    # Show stats
    with_email = len([c for c in companies if c.get("email")])
    without_email = len([c for c in companies if not c.get("email")])
    print(f"  - Со email: {with_email}")
    print(f"  - Без email: {without_email}")

    # Enrich if requested
    if args.enrich and without_email > 0:
        print(f"\nЕнричирање на {without_email} компании без email...")
        companies = await enrich_missing_emails(pool, companies, max_concurrent=3)
        with_email = len([c for c in companies if c.get("email")])
        print(f"По енричирање: {with_email} компании со email")

    # Insert targets
    companies_with_email = [c for c in companies if c.get("email")]

    if args.dry_run:
        print(f"\n[DRY RUN] Би биле додадени {len(companies_with_email)} цели")
        for c in companies_with_email[:10]:
            print(f"  - {c['company_name']}: {c['email']} ({c['wins']} победи)")
        if len(companies_with_email) > 10:
            print(f"  ... и уште {len(companies_with_email) - 10}")
    else:
        async with pool.acquire() as conn:
            inserted = 0
            for i, company in enumerate(companies_with_email):
                variant = "A" if i % 2 == 0 else "B"
                try:
                    await conn.execute("""
                        INSERT INTO campaign_targets (
                            campaign_id, company_name, company_tax_id, company_id,
                            email, subject_variant, stats, status
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')
                        ON CONFLICT DO NOTHING
                    """,
                        uuid.UUID(args.campaign_id),
                        company["company_name"],
                        company.get("company_tax_id"),
                        uuid.UUID(company["company_id"]) if company.get("company_id") else None,
                        company["email"],
                        variant,
                        json.dumps({
                            "participations": company["participations"],
                            "wins": company["wins"],
                            "total_value": company["total_value"]
                        })
                    )
                    inserted += 1
                except Exception as e:
                    pass

            await conn.execute("""
                UPDATE report_campaigns SET total_targets = $1, updated_at = NOW()
                WHERE id = $2
            """, inserted, uuid.UUID(args.campaign_id))

        print(f"\nДодадени {inserted} цели во кампањата")
        print(f"\nСледен чекор: python -m backend.cli.campaign_cli generate-reports {args.campaign_id}")

    await pool.close()


async def cmd_generate_reports(args):
    """Generate PDF reports for campaign targets"""
    from backend.services.report_generator import generate_reports_for_campaign

    pool = await get_pool()

    print(f"\nГенерирање извештаи за кампања {args.campaign_id}...")
    print(f"Лимит: {args.limit}")

    result = await generate_reports_for_campaign(pool, args.campaign_id, args.limit)

    print(f"\nРезултати:")
    print(f"  - Успешно: {result['success']}")
    print(f"  - Неуспешно: {result['failed']}")
    print(f"  - Вкупно: {result['total']}")

    if result['success'] > 0:
        print(f"\nСледен чекор: python -m backend.cli.campaign_cli activate {args.campaign_id}")

    await pool.close()


async def cmd_activate(args):
    """Activate campaign for sending"""
    pool = await get_pool()

    async with pool.acquire() as conn:
        # Check campaign
        result = await conn.fetchrow("""
            SELECT
                rc.status,
                COUNT(ct.id) as total,
                COUNT(CASE WHEN ct.report_id IS NOT NULL THEN 1 END) as with_reports
            FROM report_campaigns rc
            LEFT JOIN campaign_targets ct ON rc.id = ct.campaign_id
            WHERE rc.id = $1
            GROUP BY rc.status
        """, uuid.UUID(args.campaign_id))

        if not result:
            print(f"Кампања не е пронајдена")
            return

        if result['with_reports'] == 0:
            print(f"Нема генерирани извештаи. Прво извршете generate-reports")
            return

        await conn.execute("""
            UPDATE report_campaigns
            SET status = 'active', started_at = NOW(), updated_at = NOW()
            WHERE id = $1
        """, uuid.UUID(args.campaign_id))

    print(f"\nКампања активирана!")
    print(f"Вкупно цели: {result['total']}")
    print(f"Подготвени за испраќање: {result['with_reports']}")
    print(f"\nСледен чекор: python -m backend.cli.campaign_cli send {args.campaign_id}")

    await pool.close()


async def cmd_send(args):
    """Send campaign batch"""
    from backend.services.campaign_sender import CampaignSender

    pool = await get_pool()

    # Check campaign is active
    async with pool.acquire() as conn:
        campaign = await conn.fetchrow("""
            SELECT status FROM report_campaigns WHERE id = $1
        """, uuid.UUID(args.campaign_id))

        if not campaign:
            print("Кампања не е пронајдена")
            return

        if campaign['status'] != 'active':
            print(f"Кампањата не е активна (статус: {campaign['status']})")
            return

    sender = CampaignSender(pool)

    print(f"\nИспраќање batch од {args.batch_size} emails...")
    if args.dry_run:
        print("[DRY RUN MODE]")

    try:
        result = await sender.send_campaign_batch(
            args.campaign_id,
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )

        print(f"\nРезултати:")
        print(f"  - Испратени: {result['sent']}")
        print(f"  - Неуспешни: {result['failed']}")
        print(f"  - Скипнати (rate limit): {result['skipped_rate_limit']}")

        if result['results']:
            print(f"\nДетали:")
            for r in result['results'][:5]:
                if r.get('success') or r.get('dry_run'):
                    print(f"  OK: {r.get('company', r.get('email'))}")
                else:
                    print(f"  FAIL: {r.get('error')}")

    finally:
        await sender.close()

    await pool.close()


async def cmd_followups(args):
    """Send follow-up emails"""
    from backend.services.campaign_sender import CampaignSender

    pool = await get_pool()
    sender = CampaignSender(pool)

    print(f"\nИспраќање follow-up emails за кампања {args.campaign_id}...")
    if args.dry_run:
        print("[DRY RUN MODE]")

    try:
        result = await sender.send_followups(args.campaign_id, dry_run=args.dry_run)

        print(f"\nРезултати:")
        print(f"  - Follow-up 1: {result['followup1_sent']}")
        print(f"  - Follow-up 2: {result['followup2_sent']}")
        print(f"  - Скипнати: {result['skipped']}")

    finally:
        await sender.close()

    await pool.close()


async def cmd_status(args):
    """Show campaign status"""
    pool = await get_pool()

    async with pool.acquire() as conn:
        campaign = await conn.fetchrow("""
            SELECT * FROM report_campaigns WHERE id = $1
        """, uuid.UUID(args.campaign_id))

        if not campaign:
            print("Кампања не е пронајдена")
            return

        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'report_generated' THEN 1 END) as report_generated,
                COUNT(CASE WHEN status = 'sent' THEN 1 END) as sent,
                COUNT(CASE WHEN status = 'delivered' THEN 1 END) as delivered,
                COUNT(CASE WHEN status = 'opened' THEN 1 END) as opened,
                COUNT(CASE WHEN status = 'clicked' THEN 1 END) as clicked,
                COUNT(CASE WHEN status = 'replied' THEN 1 END) as replied,
                COUNT(CASE WHEN status = 'converted' THEN 1 END) as converted,
                COUNT(CASE WHEN status = 'unsubscribed' THEN 1 END) as unsubscribed,
                COUNT(CASE WHEN status = 'bounced' THEN 1 END) as bounced
            FROM campaign_targets WHERE campaign_id = $1
        """, uuid.UUID(args.campaign_id))

    print(f"\n{'='*50}")
    print(f"КАМПАЊА: {campaign['name']}")
    print(f"{'='*50}")
    print(f"ID: {campaign['id']}")
    print(f"Статус: {campaign['status']}")
    print(f"Креирана: {campaign['created_at']}")
    if campaign['started_at']:
        print(f"Започната: {campaign['started_at']}")

    print(f"\n--- Цели ---")
    print(f"Вкупно: {stats['total']}")
    print(f"Чека извештај: {stats['pending']}")
    print(f"Извештај готов: {stats['report_generated']}")

    print(f"\n--- Испратени ---")
    print(f"Испратени: {stats['sent']}")
    print(f"Доставени: {stats['delivered']}")

    print(f"\n--- Ангажман ---")
    print(f"Отворени: {stats['opened']}")
    print(f"Кликнати: {stats['clicked']}")
    print(f"Одговорени: {stats['replied']}")
    print(f"Конвертирани: {stats['converted']}")

    print(f"\n--- Проблеми ---")
    print(f"Одјавени: {stats['unsubscribed']}")
    print(f"Bounce: {stats['bounced']}")

    # Calculate rates
    total_sent = stats['sent'] + stats['delivered'] + stats['opened'] + stats['clicked'] + stats['replied'] + stats['converted']
    if total_sent > 0:
        open_rate = 100 * stats['opened'] / total_sent
        click_rate = 100 * stats['clicked'] / stats['opened'] if stats['opened'] > 0 else 0
        print(f"\n--- Стапки ---")
        print(f"Open rate: {open_rate:.1f}%")
        print(f"Click rate: {click_rate:.1f}%")

    await pool.close()


async def cmd_list(args):
    """List all campaigns"""
    pool = await get_pool()

    async with pool.acquire() as conn:
        if args.status:
            rows = await conn.fetch("""
                SELECT * FROM campaign_stats_view WHERE status = $1
                ORDER BY created_at DESC
            """, args.status)
        else:
            rows = await conn.fetch("""
                SELECT * FROM campaign_stats_view
                ORDER BY created_at DESC
            """)

    print(f"\n{'ID':<40} {'Име':<30} {'Статус':<10} {'Цели':<8} {'Испр.':<8} {'Отв.':<8}")
    print("-" * 110)

    for row in rows:
        print(f"{str(row['campaign_id']):<40} {row['name'][:28]:<30} {row['status']:<10} {row['actual_targets']:<8} {row['sent']:<8} {row['opened']:<8}")

    await pool.close()


def main():
    parser = argparse.ArgumentParser(
        description="Campaign CLI - Управување со report-first outreach кампањи",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Команда")

    # Create
    create_parser = subparsers.add_parser("create", help="Креирај нова кампања")
    create_parser.add_argument("--name", "-n", required=True, help="Име на кампањата")
    create_parser.add_argument("--description", "-d", help="Опис")
    create_parser.add_argument("--min-participations", type=int, default=5)
    create_parser.add_argument("--min-wins", type=int, default=2)
    create_parser.add_argument("--lookback-days", type=int, default=365)
    create_parser.add_argument("--missed-days", type=int, default=90)
    create_parser.add_argument("--attach-pdf", type=int, default=20)
    create_parser.add_argument("--daily-limit", type=int, default=100)
    create_parser.add_argument("--hourly-limit", type=int, default=20)

    # Select targets
    select_parser = subparsers.add_parser("select-targets", help="Селектирај топ компании")
    select_parser.add_argument("campaign_id", help="ID на кампањата")
    select_parser.add_argument("--limit", "-l", type=int, default=100)
    select_parser.add_argument("--enrich", action="store_true", help="Енричирај email-ови")
    select_parser.add_argument("--dry-run", action="store_true")

    # Generate reports
    gen_parser = subparsers.add_parser("generate-reports", help="Генерирај PDF извештаи")
    gen_parser.add_argument("campaign_id", help="ID на кампањата")
    gen_parser.add_argument("--limit", "-l", type=int, default=50)

    # Activate
    activate_parser = subparsers.add_parser("activate", help="Активирај кампања")
    activate_parser.add_argument("campaign_id", help="ID на кампањата")

    # Send
    send_parser = subparsers.add_parser("send", help="Испрати batch emails")
    send_parser.add_argument("campaign_id", help="ID на кампањата")
    send_parser.add_argument("--batch-size", "-b", type=int, default=10)
    send_parser.add_argument("--dry-run", action="store_true")

    # Followups
    followup_parser = subparsers.add_parser("followups", help="Испрати follow-up emails")
    followup_parser.add_argument("campaign_id", help="ID на кампањата")
    followup_parser.add_argument("--dry-run", action="store_true")

    # Status
    status_parser = subparsers.add_parser("status", help="Покажи статус на кампања")
    status_parser.add_argument("campaign_id", help="ID на кампањата")

    # List
    list_parser = subparsers.add_parser("list", help="Листа на кампањи")
    list_parser.add_argument("--status", "-s", help="Филтрирај по статус")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Run appropriate command
    commands = {
        "create": cmd_create,
        "select-targets": cmd_select_targets,
        "generate-reports": cmd_generate_reports,
        "activate": cmd_activate,
        "send": cmd_send,
        "followups": cmd_followups,
        "status": cmd_status,
        "list": cmd_list
    }

    asyncio.run(commands[args.command](args))


if __name__ == "__main__":
    main()
