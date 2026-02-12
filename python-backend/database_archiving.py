#!/usr/bin/env python3
"""
Database Archiving and Maintenance Script for 40GB Low-Disk Server

This script:
1. Archives old appointments and IVR logs to compressed JSON files
2. Vacuums SQLite database to reclaim space
3. Monitors database size
4. Maintains performance on low-resource servers

Run monthly via cron: 0 2 1 * * /path/to/database_archiving.py
"""

import sqlite3
import json
import gzip
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

# Configuration
DB_PATH = os.getenv("DATABASE_PATH", "/app/data/lb_automotive.db")
ARCHIVE_DIR = os.getenv("ARCHIVE_DIR", "/app/data/archives")
ARCHIVE_AFTER_DAYS = int(os.getenv("ARCHIVE_AFTER_DAYS", "90"))  # Archive data older than 90 days
DELETE_ARCHIVED_AFTER_DAYS = int(os.getenv("DELETE_ARCHIVED_AFTER_DAYS", "30"))  # Delete from DB 30 days after archiving


def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_size_mb() -> float:
    """Get database file size in MB"""
    if os.path.exists(DB_PATH):
        return os.path.getsize(DB_PATH) / (1024 * 1024)
    return 0.0


def archive_old_appointments(conn: sqlite3.Connection, cutoff_date: datetime) -> int:
    """Archive appointments older than cutoff_date"""
    cursor = conn.cursor()
    
    # Get appointments to archive (completed/cancelled, older than cutoff)
    cursor.execute("""
        SELECT * FROM appointments 
        WHERE date < ? 
        AND status IN ('completed', 'cancelled', 'no-show')
    """, (cutoff_date.date().isoformat(),))
    
    appointments = [dict(row) for row in cursor.fetchall()]
    
    if not appointments:
        print(f"No appointments to archive before {cutoff_date.date()}")
        return 0
    
    # Create archive file
    archive_file = Path(ARCHIVE_DIR) / f"appointments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.gz"
    archive_file.parent.mkdir(parents=True, exist_ok=True)
    
    with gzip.open(archive_file, 'wt', encoding='utf-8') as f:
        json.dump({
            "archived_at": datetime.now().isoformat(),
            "cutoff_date": cutoff_date.date().isoformat(),
            "count": len(appointments),
            "appointments": appointments
        }, f, indent=2, default=str)
    
    print(f"✓ Archived {len(appointments)} appointments to {archive_file}")
    
    # Mark as archived but don't delete yet (safe approach)
    appointment_ids = [a['id'] for a in appointments]
    placeholders = ','.join('?' * len(appointment_ids))
    cursor.execute(f"""
        UPDATE appointments 
        SET notes = COALESCE(notes || ' ', '') || '[ARCHIVED]'
        WHERE id IN ({placeholders})
    """, appointment_ids)
    
    conn.commit()
    return len(appointments)


def archive_old_ivr_logs(conn: sqlite3.Connection, cutoff_date: datetime) -> int:
    """Archive IVR logs older than cutoff_date"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM ivr_logs 
        WHERE created_at < ?
    """, (cutoff_date.isoformat(),))
    
    logs = [dict(row) for row in cursor.fetchall()]
    
    if not logs:
        print(f"No IVR logs to archive before {cutoff_date}")
        return 0
    
    # Create archive file
    archive_file = Path(ARCHIVE_DIR) / f"ivr_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.gz"
    archive_file.parent.mkdir(parents=True, exist_ok=True)
    
    with gzip.open(archive_file, 'wt', encoding='utf-8') as f:
        json.dump({
            "archived_at": datetime.now().isoformat(),
            "cutoff_date": cutoff_date.isoformat(),
            "count": len(logs),
            "logs": logs
        }, f, indent=2, default=str)
    
    print(f"✓ Archived {len(logs)} IVR logs to {archive_file}")
    
    # Delete archived IVR logs (they're not critical for operations)
    log_ids = [log['id'] for log in logs]
    placeholders = ','.join('?' * len(log_ids))
    cursor.execute(f"DELETE FROM ivr_logs WHERE id IN ({placeholders})", log_ids)
    
    conn.commit()
    return len(logs)


def delete_old_archived_records(conn: sqlite3.Connection, delete_cutoff_date: datetime) -> int:
    """Delete old archived appointments from database"""
    cursor = conn.cursor()
    
    # Only delete records that are marked as archived and very old
    cursor.execute("""
        DELETE FROM appointments 
        WHERE date < ? 
        AND status IN ('completed', 'cancelled', 'no-show')
        AND notes LIKE '%[ARCHIVED]%'
    """, (delete_cutoff_date.date().isoformat(),))
    
    deleted = cursor.rowcount
    conn.commit()
    
    if deleted > 0:
        print(f"✓ Deleted {deleted} old archived appointments from database")
    
    return deleted


def vacuum_database(conn: sqlite3.Connection):
    """Vacuum database to reclaim space"""
    print("Running VACUUM to reclaim disk space...")
    db_size_before = get_db_size_mb()
    
    conn.execute("VACUUM")
    conn.commit()
    
    db_size_after = get_db_size_mb()
    space_freed = db_size_before - db_size_after
    
    print(f"✓ VACUUM complete. Space freed: {space_freed:.2f} MB")
    print(f"  Database size: {db_size_before:.2f} MB → {db_size_after:.2f} MB")


def analyze_database(conn: sqlite3.Connection):
    """Analyze database for query optimization"""
    print("Analyzing database for optimization...")
    conn.execute("ANALYZE")
    conn.commit()
    print("✓ Analysis complete")


def get_table_stats(conn: sqlite3.Connection) -> Dict[str, int]:
    """Get row counts for major tables"""
    cursor = conn.cursor()
    stats = {}
    
    tables = ['appointments', 'customers', 'ivr_logs', 'call_states', 'staff', 'services']
    
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            stats[table] = count
        except sqlite3.OperationalError:
            stats[table] = 0
    
    return stats


def cleanup_old_archives():
    """Remove archive files older than 1 year"""
    archive_dir = Path(ARCHIVE_DIR)
    if not archive_dir.exists():
        return
    
    cutoff = datetime.now() - timedelta(days=365)
    deleted = 0
    
    for archive_file in archive_dir.glob("*.json.gz"):
        if datetime.fromtimestamp(archive_file.stat().st_mtime) < cutoff:
            archive_file.unlink()
            deleted += 1
    
    if deleted > 0:
        print(f"✓ Deleted {deleted} old archive files (>1 year)")


def main():
    """Main archiving routine"""
    print("=" * 60)
    print("Database Archiving and Maintenance")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)
    print()
    
    # Check database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return 1
    
    conn = get_db_connection()
    
    try:
        # Initial stats
        print("Initial Statistics:")
        print(f"  Database size: {get_db_size_mb():.2f} MB")
        stats = get_table_stats(conn)
        for table, count in stats.items():
            print(f"  {table}: {count:,} rows")
        print()
        
        # Archive old data
        archive_cutoff = datetime.now() - timedelta(days=ARCHIVE_AFTER_DAYS)
        delete_cutoff = datetime.now() - timedelta(days=ARCHIVE_AFTER_DAYS + DELETE_ARCHIVED_AFTER_DAYS)
        
        print(f"Archiving data older than: {archive_cutoff.date()}")
        print(f"Deleting archived data older than: {delete_cutoff.date()}")
        print()
        
        appointments_archived = archive_old_appointments(conn, archive_cutoff)
        ivr_logs_archived = archive_old_ivr_logs(conn, archive_cutoff)
        records_deleted = delete_old_archived_records(conn, delete_cutoff)
        
        print()
        
        # Maintenance
        vacuum_database(conn)
        analyze_database(conn)
        
        print()
        
        # Final stats
        print("Final Statistics:")
        print(f"  Database size: {get_db_size_mb():.2f} MB")
        final_stats = get_table_stats(conn)
        for table, count in final_stats.items():
            print(f"  {table}: {count:,} rows")
        print()
        
        # Cleanup old archives
        cleanup_old_archives()
        
        print()
        print("=" * 60)
        print("Archiving Complete!")
        print(f"  Appointments archived: {appointments_archived}")
        print(f"  IVR logs archived: {ivr_logs_archived}")
        print(f"  Records deleted: {records_deleted}")
        print(f"  Archive location: {ARCHIVE_DIR}")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"❌ Error during archiving: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        conn.close()


if __name__ == "__main__":
    exit(main())
