"""
System Monitoring Service for nabavkidata.com
Tracks system health, database stats, API metrics, and business KPIs
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
import psutil
import asyncio
import os
import logging

from database import AsyncSessionLocal, engine
from models import (
    User, Tender, Document, QueryHistory, Subscription,
    UsageTracking, AuditLog
)
from models_billing import Payment

logger = logging.getLogger(__name__)


class MonitoringService:
    """Centralized monitoring service for system health and metrics"""

    def __init__(self):
        self.api_request_count = 0
        self.api_response_times = []
        self.api_error_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_size = 0

    async def get_system_health(self) -> Dict:
        """
        Get system resource usage metrics
        Returns CPU, memory, disk usage
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Network stats
            net_io = psutil.net_io_counters()

            # Process stats
            process = psutil.Process()
            process_memory = process.memory_info()

            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "cpu": {
                    "percent": cpu_percent,
                    "count": psutil.cpu_count(),
                    "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "percent": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent": disk.percent
                },
                "network": {
                    "bytes_sent_mb": round(net_io.bytes_sent / (1024**2), 2),
                    "bytes_recv_mb": round(net_io.bytes_recv / (1024**2), 2),
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv
                },
                "process": {
                    "memory_mb": round(process_memory.rss / (1024**2), 2),
                    "threads": process.num_threads(),
                    "connections": len(process.connections())
                }
            }
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {"status": "error", "error": str(e)}

    async def get_database_stats(self) -> Dict:
        """
        Get database performance statistics
        Returns connection pool info, query count, slow queries
        """
        try:
            async with AsyncSessionLocal() as session:
                # Connection pool stats
                pool = engine.pool
                pool_size = pool.size()
                pool_checked_out = pool.checkedout()
                pool_overflow = pool.overflow()

                # Active connections
                result = await session.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                )
                active_connections = result.scalar()

                # Database size
                result = await session.execute(
                    text("SELECT pg_database_size(current_database())")
                )
                db_size_bytes = result.scalar()

                # Slow queries (queries running > 5 seconds)
                result = await session.execute(
                    text("""
                        SELECT count(*)
                        FROM pg_stat_activity
                        WHERE state = 'active'
                        AND now() - query_start > interval '5 seconds'
                    """)
                )
                slow_query_count = result.scalar()

                # Table sizes
                result = await session.execute(
                    text("""
                        SELECT
                            schemaname,
                            tablename,
                            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
                        FROM pg_tables
                        WHERE schemaname = 'public'
                        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                        LIMIT 10
                    """)
                )
                table_sizes = [
                    {"schema": row[0], "table": row[1], "size": row[2]}
                    for row in result.fetchall()
                ]

                return {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "connection_pool": {
                        "size": pool_size,
                        "checked_out": pool_checked_out,
                        "overflow": pool_overflow,
                        "active_connections": active_connections
                    },
                    "database": {
                        "size_gb": round(db_size_bytes / (1024**3), 2),
                        "slow_queries": slow_query_count
                    },
                    "top_tables": table_sizes
                }
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {"status": "error", "error": str(e)}

    async def get_cache_stats(self) -> Dict:
        """
        Get cache performance metrics
        Returns cache hit rate, size, and efficiency
        """
        try:
            total_requests = self.cache_hits + self.cache_misses
            hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0

            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "cache": {
                    "hits": self.cache_hits,
                    "misses": self.cache_misses,
                    "hit_rate_percent": round(hit_rate, 2),
                    "total_requests": total_requests,
                    "size_mb": round(self.cache_size / (1024**2), 2)
                }
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"status": "error", "error": str(e)}

    async def get_api_metrics(self) -> Dict:
        """
        Get API performance metrics
        Returns request count, response times, error rate
        """
        try:
            avg_response_time = (
                sum(self.api_response_times) / len(self.api_response_times)
                if self.api_response_times else 0
            )

            error_rate = (
                (self.api_error_count / self.api_request_count * 100)
                if self.api_request_count > 0 else 0
            )

            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "api": {
                    "total_requests": self.api_request_count,
                    "error_count": self.api_error_count,
                    "error_rate_percent": round(error_rate, 2),
                    "avg_response_time_ms": round(avg_response_time, 2),
                    "min_response_time_ms": min(self.api_response_times) if self.api_response_times else 0,
                    "max_response_time_ms": max(self.api_response_times) if self.api_response_times else 0
                }
            }
        except Exception as e:
            logger.error(f"Error getting API metrics: {e}")
            return {"status": "error", "error": str(e)}

    def log_api_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time: float
    ):
        """
        Log API request metrics

        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST, etc.)
            status_code: HTTP response status code
            response_time: Response time in milliseconds
        """
        try:
            self.api_request_count += 1
            self.api_response_times.append(response_time)

            # Keep only last 1000 response times to prevent memory bloat
            if len(self.api_response_times) > 1000:
                self.api_response_times = self.api_response_times[-1000:]

            if status_code >= 400:
                self.api_error_count += 1

            logger.info(
                f"API Request: {method} {endpoint} - {status_code} - {response_time}ms"
            )
        except Exception as e:
            logger.error(f"Error logging API request: {e}")

    async def get_user_activity(self) -> Dict:
        """
        Get user activity metrics
        Returns active users, new signups, churn
        """
        try:
            async with AsyncSessionLocal() as session:
                # Total users
                result = await session.execute(select(func.count(User.user_id)))
                total_users = result.scalar()

                # New users today
                today = datetime.utcnow().date()
                result = await session.execute(
                    select(func.count(User.user_id)).where(
                        func.date(User.created_at) == today
                    )
                )
                new_today = result.scalar()

                # New users this week
                week_ago = datetime.utcnow() - timedelta(days=7)
                result = await session.execute(
                    select(func.count(User.user_id)).where(
                        User.created_at >= week_ago
                    )
                )
                new_this_week = result.scalar()

                # Active users (users with activity in last 30 days)
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                result = await session.execute(
                    select(func.count(func.distinct(UsageTracking.user_id))).where(
                        UsageTracking.timestamp >= thirty_days_ago
                    )
                )
                active_users_30d = result.scalar()

                # Verified emails
                result = await session.execute(
                    select(func.count(User.user_id)).where(User.email_verified == True)
                )
                verified_users = result.scalar()

                return {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "users": {
                        "total": total_users,
                        "new_today": new_today,
                        "new_this_week": new_this_week,
                        "active_30d": active_users_30d,
                        "verified": verified_users,
                        "verification_rate_percent": round((verified_users / total_users * 100) if total_users > 0 else 0, 2)
                    }
                }
        except Exception as e:
            logger.error(f"Error getting user activity: {e}")
            return {"status": "error", "error": str(e)}

    async def get_revenue_stats(self) -> Dict:
        """
        Get revenue and subscription metrics
        Returns MRR, ARR, conversion rate
        """
        try:
            async with AsyncSessionLocal() as session:
                # Active subscriptions by tier
                result = await session.execute(
                    select(
                        Subscription.tier,
                        func.count(Subscription.subscription_id)
                    ).where(
                        Subscription.status == 'active'
                    ).group_by(Subscription.tier)
                )
                active_subs = {row[0]: row[1] for row in result.fetchall()}

                # Calculate MRR (assuming pricing)
                pricing = {"basic": 19, "professional": 49, "enterprise": 199}
                mrr = sum(active_subs.get(tier, 0) * price for tier, price in pricing.items())
                arr = mrr * 12

                # Total users for conversion rate
                result = await session.execute(select(func.count(User.user_id)))
                total_users = result.scalar()

                total_paid = sum(active_subs.values())
                conversion_rate = (total_paid / total_users * 100) if total_users > 0 else 0

                # Revenue this month (from payments)
                first_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
                result = await session.execute(
                    select(func.sum(Payment.amount)).where(
                        Payment.created_at >= first_of_month,
                        Payment.status == 'succeeded'
                    )
                )
                revenue_this_month = result.scalar() or 0

                return {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "revenue": {
                        "mrr_usd": round(mrr, 2),
                        "arr_usd": round(arr, 2),
                        "revenue_this_month_usd": round(float(revenue_this_month), 2),
                        "conversion_rate_percent": round(conversion_rate, 2)
                    },
                    "subscriptions": {
                        "active_by_tier": active_subs,
                        "total_active": total_paid
                    }
                }
        except Exception as e:
            logger.error(f"Error getting revenue stats: {e}")
            return {"status": "error", "error": str(e)}

    async def get_tender_stats(self) -> Dict:
        """
        Get tender statistics
        Returns total tenders, new today, breakdown by category
        """
        try:
            async with AsyncSessionLocal() as session:
                # Total tenders
                result = await session.execute(select(func.count(Tender.tender_id)))
                total_tenders = result.scalar()

                # New tenders today
                today = datetime.utcnow().date()
                result = await session.execute(
                    select(func.count(Tender.tender_id)).where(
                        func.date(Tender.created_at) == today
                    )
                )
                new_today = result.scalar()

                # Tenders by status
                result = await session.execute(
                    select(
                        Tender.status,
                        func.count(Tender.tender_id)
                    ).group_by(Tender.status)
                )
                by_status = {row[0]: row[1] for row in result.fetchall()}

                # Top 10 categories
                result = await session.execute(
                    select(
                        Tender.category,
                        func.count(Tender.tender_id)
                    ).where(
                        Tender.category.isnot(None)
                    ).group_by(Tender.category).order_by(
                        func.count(Tender.tender_id).desc()
                    ).limit(10)
                )
                top_categories = [
                    {"category": row[0], "count": row[1]}
                    for row in result.fetchall()
                ]

                # Total value (EUR)
                result = await session.execute(
                    select(func.sum(Tender.estimated_value_eur)).where(
                        Tender.estimated_value_eur.isnot(None)
                    )
                )
                total_value_eur = result.scalar() or 0

                return {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "tenders": {
                        "total": total_tenders,
                        "new_today": new_today,
                        "by_status": by_status,
                        "total_value_eur": round(float(total_value_eur), 2),
                        "top_categories": top_categories
                    }
                }
        except Exception as e:
            logger.error(f"Error getting tender stats: {e}")
            return {"status": "error", "error": str(e)}

    async def get_scraper_metrics(self) -> Dict:
        """
        Get web scraper performance metrics
        Returns last run time, success rate, errors
        """
        try:
            async with AsyncSessionLocal() as session:
                # Get latest scrape timestamp
                result = await session.execute(
                    select(func.max(Tender.scraped_at))
                )
                last_scrape = result.scalar()

                # Count recent scrapes (last 24 hours)
                yesterday = datetime.utcnow() - timedelta(days=1)
                result = await session.execute(
                    select(func.count(Tender.tender_id)).where(
                        Tender.scraped_at >= yesterday
                    )
                )
                scraped_24h = result.scalar()

                # Documents extracted
                result = await session.execute(
                    select(func.count(Document.doc_id)).where(
                        Document.extraction_status == 'completed'
                    )
                )
                documents_extracted = result.scalar()

                # Documents pending
                result = await session.execute(
                    select(func.count(Document.doc_id)).where(
                        Document.extraction_status == 'pending'
                    )
                )
                documents_pending = result.scalar()

                # Documents failed
                result = await session.execute(
                    select(func.count(Document.doc_id)).where(
                        Document.extraction_status == 'failed'
                    )
                )
                documents_failed = result.scalar()

                total_docs = documents_extracted + documents_failed
                success_rate = (documents_extracted / total_docs * 100) if total_docs > 0 else 0

                return {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "scraper": {
                        "last_run": last_scrape.isoformat() if last_scrape else None,
                        "tenders_scraped_24h": scraped_24h,
                        "documents": {
                            "extracted": documents_extracted,
                            "pending": documents_pending,
                            "failed": documents_failed,
                            "success_rate_percent": round(success_rate, 2)
                        }
                    }
                }
        except Exception as e:
            logger.error(f"Error getting scraper metrics: {e}")
            return {"status": "error", "error": str(e)}

    async def trigger_alert(self, level: str, message: str):
        """
        Trigger system alert

        Args:
            level: Alert level (info, warning, error, critical)
            message: Alert message
        """
        try:
            logger.log(
                {
                    "info": logging.INFO,
                    "warning": logging.WARNING,
                    "error": logging.ERROR,
                    "critical": logging.CRITICAL
                }.get(level, logging.INFO),
                f"ALERT [{level.upper()}]: {message}"
            )

            # TODO: Implement email alerts
            # TODO: Implement Slack notifications

            return {
                "status": "sent",
                "level": level,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error triggering alert: {e}")
            return {"status": "error", "error": str(e)}


# Singleton instance
monitoring_service = MonitoringService()
