"""
Migration script to add month_year column to existing database
and populate it from existing date values.

Run this ONCE before using the updated app.py
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Integer, String, Float, text
import os

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create a temporary app for migration
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///milk-calculation.db"
db.init_app(app)

def migrate():
    with app.app_context():
        try:
            # Step 1: Check if month_year column already exists
            result = db.session.execute(text("PRAGMA table_info(milk)"))
            columns = [row[1] for row in result]
            
            if 'month_year' in columns:
                print("✓ Column 'month_year' already exists. Checking for NULL values...")
            else:
                print("Adding 'month_year' column to milk table...")
                # Add the new column
                db.session.execute(text("ALTER TABLE milk ADD COLUMN month_year VARCHAR(50)"))
                db.session.commit()
                print("✓ Column 'month_year' added successfully!")
            
            # Step 2: Populate month_year from existing date values
            print("\nPopulating month_year from existing dates...")
            result = db.session.execute(text("SELECT id, date FROM milk WHERE month_year IS NULL OR month_year = ''"))
            records = result.fetchall()
            
            updated_count = 0
            error_count = 0
            
            for record in records:
                record_id, date_str = record
                
                if date_str:
                    # Parse DD-MM-YYYY format
                    parts = date_str.split('-')
                    if len(parts) == 3:
                        # Extract MM-YYYY
                        month_year = f"{parts[1]}-{parts[2]}"
                        
                        # Update the record
                        db.session.execute(
                            text("UPDATE milk SET month_year = :month_year WHERE id = :id"),
                            {"month_year": month_year, "id": record_id}
                        )
                        updated_count += 1
                        print(f"  Record {record_id}: {date_str} → {month_year}")
                    else:
                        print(f"  ⚠ Record {record_id}: Invalid date format '{date_str}'")
                        error_count += 1
                else:
                    print(f"  ⚠ Record {record_id}: No date found")
                    error_count += 1
            
            db.session.commit()
            
            # Step 3: Drop the total_cost column if it exists (optional cleanup)
            print("\n" + "="*50)
            if 'total_cost' in columns:
                response = input("Do you want to remove the old 'total_cost' column? (y/n): ").lower()
                if response == 'y':
                    print("Removing 'total_cost' column...")
                    # SQLite doesn't support DROP COLUMN directly, need to recreate table
                    print("⚠ SQLite requires table recreation to drop columns.")
                    print("Skipping this step. The column will remain but won't be used.")
                    print("If you want to remove it, delete the database and start fresh.")
            
            # Summary
            print("\n" + "="*50)
            print("MIGRATION SUMMARY")
            print("="*50)
            print(f"✓ Records updated: {updated_count}")
            if error_count > 0:
                print(f"⚠ Records with errors: {error_count}")
            print("\n✓ Migration completed successfully!")
            print("\nYou can now run your updated app.py")
            
        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            db.session.rollback()
            return False
    
    return True

if __name__ == "__main__":
    print("="*50)
    print("DATABASE MIGRATION SCRIPT")
    print("="*50)
    print("\nThis script will:")
    print("1. Add 'month_year' column to the milk table")
    print("2. Populate month_year from existing date values")
    print("3. Optionally remove the old 'total_cost' column")
    print("\n⚠ IMPORTANT: Backup your database before proceeding!")
    print(f"Database location: instance/milk-calculation.db")
    
    # Check if database exists
    db_path = "instance/milk-calculation.db"
    if not os.path.exists(db_path):
        print(f"\n✗ Database not found at {db_path}")
        print("Please make sure the database file exists in the correct location.")
    else:
        response = input("\nDo you want to proceed with the migration? (y/n): ").lower()
        
        if response == 'y':
            print("\nStarting migration...\n")
            success = migrate()
            if success:
                print("\n" + "="*50)
                print("All done! You can now start your Flask app.")
                print("="*50)
        else:
            print("\nMigration cancelled.")
