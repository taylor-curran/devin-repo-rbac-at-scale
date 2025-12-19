"""
volume_estimator.py - Estimate Splunk Storage Requirements

This script helps answer the Splunk team's first question:
"How much data will this generate?"

It samples a time window of real data and projects:
- Events per day by type
- Average payload size by type
- Total GB/day and GB/month estimates

Run this against a pilot user population to get realistic estimates
before rolling out enterprise-wide.

Usage:
    python volume_estimator.py --hours 24
    python volume_estimator.py --hours 168 --users 50  # 1 week, project for 50 users
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

# ========== CONFIGURATION ==========
ADMIN_API_KEY = os.getenv("DEVIN_ADMIN_USER_API_KEY")
SERVICE_API_KEY = os.getenv("DEVIN_SERVICE_ACCOUNT_API_KEY")

V2_BASE_URL = "https://api.devin.ai/v2"
V3_BASE_URL = "https://api.devin.ai/v3beta1"


@dataclass
class VolumeStats:
    """Tracks volume statistics for a data type."""
    event_count: int = 0
    total_bytes: int = 0
    sample_hours: float = 0
    
    @property
    def avg_bytes_per_event(self) -> float:
        if self.event_count == 0:
            return 0
        return self.total_bytes / self.event_count
    
    @property
    def events_per_day(self) -> float:
        if self.sample_hours == 0:
            return 0
        return (self.event_count / self.sample_hours) * 24
    
    @property
    def bytes_per_day(self) -> float:
        if self.sample_hours == 0:
            return 0
        return (self.total_bytes / self.sample_hours) * 24
    
    @property
    def gb_per_month(self) -> float:
        return (self.bytes_per_day * 30) / (1024 ** 3)


# ========== DATA COLLECTION ==========
def sample_audit_logs(hours: int) -> Dict[str, VolumeStats]:
    """
    Sample audit logs for the specified time window.
    
    Returns stats broken down by action type.
    """
    print(f"\n[AUDIT LOGS] Sampling last {hours} hours...")
    
    time_before = int(time.time())
    time_after = time_before - (hours * 3600)
    
    url = f"{V3_BASE_URL}/enterprise/audit-logs"
    headers = {
        "Authorization": f"Bearer {SERVICE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    stats_by_action: Dict[str, VolumeStats] = {}
    cursor = None
    total_events = 0
    
    while True:
        params = {
            "time_after": time_after,
            "time_before": time_before,
            "first": 200
        }
        if cursor:
            params["after"] = cursor
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            page = response.json()
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] Failed to fetch audit logs: {e}")
            break
        
        for item in page.get("items", []):
            action = item.get("action", "unknown")
            
            if action not in stats_by_action:
                stats_by_action[action] = VolumeStats(sample_hours=hours)
            
            stats = stats_by_action[action]
            stats.event_count += 1
            stats.total_bytes += len(json.dumps(item))
            total_events += 1
        
        if not page.get("has_next_page"):
            break
        cursor = page.get("end_cursor")
    
    print(f"[AUDIT LOGS] Found {total_events} events across {len(stats_by_action)} action types")
    
    return stats_by_action


def sample_sessions(hours: int) -> VolumeStats:
    """
    Sample session insights for the specified time window.
    
    Returns aggregate stats for sessions.
    """
    print(f"\n[SESSIONS] Sampling last {hours} hours...")
    
    updated_after = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    
    url = f"{V2_BASE_URL}/enterprise/sessions/insights"
    headers = {
        "Authorization": f"Bearer {ADMIN_API_KEY}",
        "Content-Type": "application/json"
    }
    
    stats = VolumeStats(sample_hours=hours)
    skip = 0
    limit = 100
    
    while True:
        params = {
            "updated_date_from": updated_after,
            "skip": skip,
            "limit": limit
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            page = response.json()
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] Failed to fetch sessions: {e}")
            break
        
        for item in page.get("items", []):
            stats.event_count += 1
            stats.total_bytes += len(json.dumps(item))
        
        if not page.get("has_more"):
            break
        skip += limit
        
        if skip > 5000:
            print("[WARN] Hit pagination limit")
            break
    
    print(f"[SESSIONS] Found {stats.event_count} sessions")
    
    return stats


# ========== PROJECTION ==========
def generate_estimate(
    audit_stats: Dict[str, VolumeStats],
    session_stats: VolumeStats,
    current_users: int,
    projected_users: int
) -> Dict[str, Any]:
    """
    Generate volume estimates with user count projection.
    
    Args:
        audit_stats: Stats by audit action type
        session_stats: Session volume stats
        current_users: Users in sample population
        projected_users: Target user population
    
    Returns:
        Complete estimate report
    """
    scale_factor = projected_users / current_users if current_users > 0 else 1
    
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_parameters": {
            "current_users": current_users,
            "projected_users": projected_users,
            "scale_factor": round(scale_factor, 2)
        },
        "audit_logs": {},
        "sessions": {},
        "totals": {}
    }
    
    # Audit log breakdown
    total_audit_events_day = 0
    total_audit_bytes_day = 0
    
    for action, stats in sorted(audit_stats.items(), key=lambda x: x[1].event_count, reverse=True):
        events_day = stats.events_per_day * scale_factor
        bytes_day = stats.bytes_per_day * scale_factor
        total_audit_events_day += events_day
        total_audit_bytes_day += bytes_day
        
        report["audit_logs"][action] = {
            "sample_count": stats.event_count,
            "avg_bytes": round(stats.avg_bytes_per_event),
            "events_per_day": round(events_day, 1),
            "mb_per_day": round(bytes_day / (1024**2), 2),
            "gb_per_month": round((bytes_day * 30) / (1024**3), 3)
        }
    
    report["audit_logs"]["_total"] = {
        "events_per_day": round(total_audit_events_day, 1),
        "mb_per_day": round(total_audit_bytes_day / (1024**2), 2),
        "gb_per_month": round((total_audit_bytes_day * 30) / (1024**3), 3)
    }
    
    # Session insights
    session_events_day = session_stats.events_per_day * scale_factor
    session_bytes_day = session_stats.bytes_per_day * scale_factor
    
    report["sessions"] = {
        "sample_count": session_stats.event_count,
        "avg_bytes": round(session_stats.avg_bytes_per_event),
        "events_per_day": round(session_events_day, 1),
        "mb_per_day": round(session_bytes_day / (1024**2), 2),
        "gb_per_month": round((session_bytes_day * 30) / (1024**3), 3)
    }
    
    # Grand totals
    total_bytes_day = total_audit_bytes_day + session_bytes_day
    report["totals"] = {
        "events_per_day": round(total_audit_events_day + session_events_day, 1),
        "mb_per_day": round(total_bytes_day / (1024**2), 2),
        "gb_per_day": round(total_bytes_day / (1024**3), 4),
        "gb_per_month": round((total_bytes_day * 30) / (1024**3), 3),
        "gb_per_year": round((total_bytes_day * 365) / (1024**3), 2)
    }
    
    return report


def print_report(report: Dict[str, Any]) -> None:
    """Print a formatted volume estimate report."""
    print("\n" + "=" * 70)
    print("SPLUNK VOLUME ESTIMATE")
    print("=" * 70)
    
    params = report["sample_parameters"]
    print(f"\nProjection: {params['current_users']} users → {params['projected_users']} users")
    print(f"Scale factor: {params['scale_factor']}x")
    
    print("\n" + "-" * 70)
    print("AUDIT LOGS (by action type)")
    print("-" * 70)
    print(f"{'Action':<35} {'Events/Day':>12} {'MB/Day':>10} {'GB/Month':>10}")
    print("-" * 70)
    
    for action, stats in report["audit_logs"].items():
        if action == "_total":
            continue
        print(f"{action:<35} {stats['events_per_day']:>12.1f} {stats['mb_per_day']:>10.2f} {stats['gb_per_month']:>10.3f}")
    
    total = report["audit_logs"]["_total"]
    print("-" * 70)
    print(f"{'AUDIT TOTAL':<35} {total['events_per_day']:>12.1f} {total['mb_per_day']:>10.2f} {total['gb_per_month']:>10.3f}")
    
    print("\n" + "-" * 70)
    print("SESSION INSIGHTS")
    print("-" * 70)
    sess = report["sessions"]
    print(f"Sessions per day: {sess['events_per_day']:.1f}")
    print(f"Avg session size: {sess['avg_bytes']:,} bytes")
    print(f"MB per day: {sess['mb_per_day']:.2f}")
    print(f"GB per month: {sess['gb_per_month']:.3f}")
    
    print("\n" + "=" * 70)
    print("GRAND TOTALS")
    print("=" * 70)
    totals = report["totals"]
    print(f"Events per day:  {totals['events_per_day']:,.0f}")
    print(f"MB per day:      {totals['mb_per_day']:,.2f}")
    print(f"GB per day:      {totals['gb_per_day']:.4f}")
    print(f"GB per month:    {totals['gb_per_month']:.3f}")
    print(f"GB per year:     {totals['gb_per_year']:.2f}")
    print("=" * 70)
    
    # Recommendations
    print("\nRECOMMENDATIONS:")
    if totals['gb_per_month'] < 1:
        print("✅ Low volume - standard Splunk tier should be sufficient")
    elif totals['gb_per_month'] < 10:
        print("⚠️  Moderate volume - consider data tiering or retention policies")
    else:
        print("🔴 High volume - recommend filtering to high-signal events only")
    
    print("\nNote: Estimates based on sample data. Actual usage may vary.")
    print("      Consider adding 20-30% buffer for production capacity.")


# ========== ENTRY POINT ==========
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Estimate Splunk storage requirements for Devin audit/session data",
        epilog="Example: python volume_estimator.py --hours 24 --users 100"
    )
    parser.add_argument("--hours", type=int, default=24, help="Sample window in hours (default: 24)")
    parser.add_argument("--users", type=int, default=None, help="Project to this many users (default: use sample)")
    parser.add_argument("--current-users", type=int, default=10, help="Current user count in sample (default: 10)")
    parser.add_argument("--save", type=str, help="Save report to JSON file")
    args = parser.parse_args()
    
    # Validate API keys
    if not SERVICE_API_KEY:
        print("[ERROR] DEVIN_SERVICE_ACCOUNT_API_KEY not set")
        exit(1)
    if not ADMIN_API_KEY:
        print("[ERROR] DEVIN_ADMIN_USER_API_KEY not set")
        exit(1)
    
    # Sample data
    print(f"Sampling {args.hours} hours of data...")
    audit_stats = sample_audit_logs(args.hours)
    session_stats = sample_sessions(args.hours)
    
    # Generate estimate
    projected_users = args.users if args.users else args.current_users
    report = generate_estimate(
        audit_stats,
        session_stats,
        current_users=args.current_users,
        projected_users=projected_users
    )
    
    # Output
    print_report(report)
    
    if args.save:
        with open(args.save, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n[SAVED] Report saved to: {args.save}")
