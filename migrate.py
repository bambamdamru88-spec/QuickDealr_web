#!/usr/bin/env python3
"""
migrate.py — QuickDealr v6 → v7 Database Migration
Run once: python3 migrate.py

Safe to re-run (uses IF NOT EXISTS / IGNORE patterns).
"""
import os, sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'quickdealr.db')

def col_exists(cur, table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())

def table_exists(cur, table):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return bool(cur.fetchone())

def run():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH} — nothing to migrate.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    changes = 0

    # 1. products.status column (was missing in some v6 builds)
    if not col_exists(cur, 'products', 'status'):
        cur.execute("ALTER TABLE products ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
        # Back-fill from approved flag
        cur.execute("UPDATE products SET status='approved' WHERE approved=1")
        cur.execute("UPDATE products SET status='pending'  WHERE approved=0")
        print("  + products.status column added and back-filled")
        changes += 1

    # 2. auction_winners table
    if not table_exists(cur, 'auction_winners'):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS auction_winners (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id       INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                winner_user_id   INTEGER NOT NULL REFERENCES users(id),
                winner_username  TEXT    NOT NULL,
                bid_amount       REAL    NOT NULL,
                rank             INTEGER NOT NULL DEFAULT 1,
                status           TEXT    NOT NULL DEFAULT 'pending_payment'
                                 CHECK(status IN ('pending_payment','paid','failed','skipped')),
                payment_deadline TIMESTAMP,
                paid_at          TIMESTAMP,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  + auction_winners table created")
        changes += 1

    # 3. Index on auction_winners for fast lookups
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_aw_product
        ON auction_winners(product_id, rank)
    """)

    # 4. Remove any admin wallet_credit / wallet_deduct entries from security_log
    #    (optional cleanup — just informational)
    cur.execute("SELECT COUNT(*) FROM security_log WHERE action IN ('admin_credit','admin_debit')")
    n = cur.fetchone()[0]
    if n:
        print(f"  ~ {n} admin wallet action log entries remain (read-only, not deleted)")

    conn.commit()
    conn.close()

    if changes:
        print(f"\nMigration complete — {changes} change(s) applied.")
    else:
        print("\nDatabase is already up to date — no changes needed.")

if __name__ == '__main__':
    print(f"Migrating: {DB_PATH}\n")
    run()


# v7 Enhancement migrations
def migrate_v7(db):
    """Add is_whitelisted column and uploaded_files table."""
    try:
        db.execute("ALTER TABLE users ADD COLUMN is_whitelisted INTEGER NOT NULL DEFAULT 0")
        print("  [+] Added is_whitelisted column to users")
    except Exception:
        pass  # Column already exists
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                original_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                size_bytes INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()
        print("  [+] Created uploaded_files table")
    except Exception as e:
        print(f"  [!] uploaded_files: {e}")

if __name__ == '__main__':
    import sqlite3, os
    db_path = os.path.join(os.path.dirname(__file__), 'quickdealr.db')
    conn = sqlite3.connect(db_path)
    migrate_v7(conn)
    conn.close()
    print("Migration complete.")
