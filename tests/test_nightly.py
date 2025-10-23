#!/usr/bin/env python3
"""
Nightly tests for MiniChess - includes database migration and edge cases.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai


class TestDatabaseMigration(unittest.TestCase):
    """Test cases for database schema migration from old to new format."""
    
    def setUp(self):
        """Create a temporary database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        
        # Store original DB_PATH and replace it with temp path
        self.original_db_path = ai.DB_PATH
        ai.DB_PATH = self.temp_db_path
    
    def tearDown(self):
        """Clean up temporary database."""
        ai.DB_PATH = self.original_db_path
        try:
            os.unlink(self.temp_db_path)
        except:
            pass
    
    def test_old_schema_migration(self):
        """Test that old database schema without depth column is migrated correctly."""
        # Create old schema (without depth column)
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE move_cache (
                hash TEXT PRIMARY KEY,
                best_move_repr TEXT NOT NULL
            )
        ''')
        # Add some test data
        cursor.execute("INSERT INTO move_cache (hash, best_move_repr) VALUES (?, ?)", 
                      ('test_hash_1', "Move(...)"))
        cursor.execute("INSERT INTO move_cache (hash, best_move_repr) VALUES (?, ?)", 
                      ('test_hash_2', "Move(...)"))
        conn.commit()
        conn.close()
        
        # Verify old schema exists
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(move_cache)")
        columns = [col[1] for col in cursor.fetchall()]
        conn.close()
        
        self.assertIn('hash', columns)
        self.assertIn('best_move_repr', columns)
        self.assertNotIn('depth', columns, "Old schema should not have depth column")
        
        # Run setup_db which should detect and migrate the schema
        ai.setup_db()
        
        # Verify new schema with depth column
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(move_cache)")
        columns = [col[1] for col in cursor.fetchall()]
        conn.close()
        
        self.assertIn('hash', columns, "New schema should have hash column")
        self.assertIn('depth', columns, "New schema should have depth column")
        self.assertIn('best_move_repr', columns, "New schema should have best_move_repr column")
    
    def test_loading_with_missing_depth_column(self):
        """Reproduce the exact error: 'no such column: depth'."""
        # Create old schema without depth column
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE move_cache (
                hash TEXT PRIMARY KEY,
                best_move_repr TEXT NOT NULL
            )
        ''')
        cursor.execute("INSERT INTO move_cache (hash, best_move_repr) VALUES (?, ?)", 
                      ('hash1', "Move(...)"))
        conn.commit()
        conn.close()
        
        # Attempt to load without migration - should fail with old code
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        
        with self.assertRaises(sqlite3.OperationalError) as context:
            cursor.execute("SELECT hash, depth, best_move_repr FROM move_cache")
        
        self.assertIn("no such column: depth", str(context.exception).lower())
        conn.close()
        
        # Now run setup_db to migrate
        ai.setup_db()
        
        # Verify the query now works
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT hash, depth, best_move_repr FROM move_cache")
            cursor.fetchall()
            success = True
        except sqlite3.OperationalError:
            success = False
        finally:
            conn.close()
        
        self.assertTrue(success, "After migration, SELECT with depth column should work")
    
    def test_new_schema_not_affected(self):
        """Test that databases with correct schema are not modified."""
        # Create correct schema
        ai.setup_db()
        
        # Add test data
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO move_cache (hash, depth, best_move_repr) VALUES (?, ?, ?)",
                      ('test_hash', 5, "Move(...)"))
        cursor.execute("SELECT COUNT(*) FROM move_cache")
        count_before = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        
        # Run setup_db again
        ai.setup_db()
        
        # Verify data is preserved (table wasn't dropped)
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM move_cache")
        count_after = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(count_before, count_after, 
                        "Correct schema should not trigger migration")
    
    def test_load_and_save_cache_after_migration(self):
        """Test that cache operations work correctly after migration."""
        # Create old schema
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE move_cache (
                hash TEXT PRIMARY KEY,
                best_move_repr TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
        
        # Migrate schema
        ai.setup_db()
        
        # Test saving cache with new schema
        test_cache = {
            ('hash1', 3): "Move(0, 0, 1, 0)",
            ('hash2', 5): "Move(1, 1, 2, 2)",
            ('hash3', 4): "Move(2, 0, 3, 0)"
        }
        
        ai.save_move_cache_to_db(test_cache)
        
        # Test loading cache
        ai.move_cache = {}
        ai.load_move_cache_from_db()
        
        self.assertEqual(len(ai.move_cache), 3, "Should load 3 cache entries")
        self.assertIn(('hash1', 3), ai.move_cache)
        self.assertIn(('hash2', 5), ai.move_cache)
        self.assertIn(('hash3', 4), ai.move_cache)


class TestDatabaseOperations(unittest.TestCase):
    """Test database operations with correct schema."""
    
    def setUp(self):
        """Create a temporary database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        
        self.original_db_path = ai.DB_PATH
        ai.DB_PATH = self.temp_db_path
        ai.setup_db()
    
    def tearDown(self):
        """Clean up temporary database."""
        ai.DB_PATH = self.original_db_path
        try:
            os.unlink(self.temp_db_path)
        except:
            pass
    
    def test_cache_with_different_depths(self):
        """Test that cache correctly handles same position at different depths."""
        test_cache = {
            ('position_abc', 3): "Move(0, 0, 1, 0)",
            ('position_abc', 5): "Move(0, 0, 2, 0)",  # Same position, different depth
            ('position_xyz', 3): "Move(1, 1, 2, 2)"
        }
        
        ai.save_move_cache_to_db(test_cache)
        ai.move_cache = {}
        ai.load_move_cache_from_db()
        
        self.assertEqual(len(ai.move_cache), 3, "Should store separate entries for different depths")
        self.assertNotEqual(ai.move_cache[('position_abc', 3)], 
                           ai.move_cache[('position_abc', 5)],
                           "Same position at different depths should have different moves")


if __name__ == '__main__':
    unittest.main()
