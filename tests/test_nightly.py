#!/usr/bin/env python3
"""
Nightly tests for MiniChess - includes database operations and cache verification.
Updated for the Rust engine backend (minichess_engine).
"""

import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai

DB_PATH = "move_cache.db"


class TestDatabaseMigration(unittest.TestCase):
    """Test cases for database schema migration from old to new format."""

    def test_setup_db_creates_correct_schema(self):
        """Test that setup_db creates a table with hash, depth, best_move_repr."""
        ai.setup_db()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(move_cache)")
        columns = [col[1] for col in cursor.fetchall()]
        conn.close()

        self.assertIn('hash', columns, "Schema should have hash column")
        self.assertIn('depth', columns, "Schema should have depth column")
        self.assertIn('best_move_repr', columns, "Schema should have best_move_repr column")

    def test_old_schema_migration(self):
        """Test that old database schema without depth column gets replaced."""
        # Create old schema directly
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS move_cache")
        cursor.execute('''
            CREATE TABLE move_cache (
                hash TEXT PRIMARY KEY,
                best_move_repr TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

        # Run setup_db which should detect and migrate
        ai.setup_db()

        # Verify new schema
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(move_cache)")
        columns = [col[1] for col in cursor.fetchall()]
        conn.close()

        self.assertIn('depth', columns, "After migration, schema should have depth column")


class TestDatabaseOperations(unittest.TestCase):
    """Test database operations with Rust engine cache."""

    def test_save_and_load_cache(self):
        """Test that cache entries survive save/load cycle."""
        ai.setup_db()

        # Insert test data directly
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO move_cache (hash, depth, best_move_repr) VALUES (?, ?, ?)",
                      ('test_hash_nightly_1', 3, "((0, 0), (1, 0), None)"))
        cursor.execute("INSERT OR REPLACE INTO move_cache (hash, depth, best_move_repr) VALUES (?, ?, ?)",
                      ('test_hash_nightly_1', 5, "((0, 0), (2, 0), None)"))
        conn.commit()
        conn.close()

        # Load through Rust and save back
        ai.load_move_cache_from_db()
        ai.save_move_cache_to_db()

        # Verify data survives
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT hash, depth, best_move_repr FROM move_cache WHERE hash = 'test_hash_nightly_1'")
        rows = cursor.fetchall()
        conn.close()

        self.assertEqual(len(rows), 2, "Should have 2 entries for same hash at different depths")

        # Clean up test data
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM move_cache WHERE hash LIKE 'test_hash_nightly%'")
        conn.commit()
        conn.close()


if __name__ == '__main__':
    unittest.main()
