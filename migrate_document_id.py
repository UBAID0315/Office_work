"""
Migration: Convert documents.id from bigint AUTO_INCREMENT to VARCHAR(20) pattern.
Pattern: DOC_CNIC_0001, DOC_NAF_0001, DOC_PROPOSAL_0001

This script:
1. Drops all FK constraints referencing documents(id)
2. Alters documents.id from bigint to VARCHAR(20)
3. Alters all child tables' document_id from bigint to VARCHAR(20)
4. Adds document_id to cnic_data
5. Recreates all FK constraints
"""

from database.connection import create_connection

def run_migration():
    conn = create_connection()
    if not conn:
        print("❌ Failed to connect to database.")
        return
    
    cur = conn.cursor()

    # All tables that have document_id FK → documents(id)
    NAF_TABLES = [
        "naf_basic_information",
        "naf_family_details",
        "naf_dependents",
        "naf_employment_details",
        "naf_financial_details",
        "naf_pension_details",
        "naf_future_saving_needs",
        "naf_family_takaful_plans",
        "naf_financial_priorities",
        "naf_identified_takaful_needs",
        "naf_recommendation",
    ]

    try:
        # ── Step 1: Drop all FK constraints on NAF tables ──────────────────
        print("Step 1: Dropping FK constraints...")
        for table in NAF_TABLES:
            cur.execute(f"""
                SELECT CONSTRAINT_NAME 
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = '{table}' 
                  AND COLUMN_NAME = 'document_id'
                  AND REFERENCED_TABLE_NAME = 'documents'
            """)
            constraints = cur.fetchall()
            for (fk_name,) in constraints:
                cur.execute(f"ALTER TABLE `{table}` DROP FOREIGN KEY `{fk_name}`")
                print(f"  Dropped FK `{fk_name}` from `{table}`")

        # ── Step 2: Alter documents.id from bigint to VARCHAR(20) ──────────
        print("\nStep 2: Altering documents.id...")
        cur.execute("""
            ALTER TABLE `documents` 
            MODIFY COLUMN `id` VARCHAR(20) NOT NULL
        """)
        print("  documents.id → VARCHAR(20) ✓")

        # ── Step 3: Alter all NAF tables' document_id to VARCHAR(20) ───────
        print("\nStep 3: Altering NAF tables document_id...")
        for table in NAF_TABLES:
            cur.execute(f"""
                ALTER TABLE `{table}` 
                MODIFY COLUMN `document_id` VARCHAR(20) NOT NULL
            """)
            print(f"  {table}.document_id → VARCHAR(20) ✓")

        # ── Step 4: Add document_id to cnic_data ───────────────────────────
        print("\nStep 4: Adding document_id to cnic_data...")
        # Check if column already exists
        cur.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
              AND TABLE_NAME = 'cnic_data' 
              AND COLUMN_NAME = 'document_id'
        """)
        if cur.fetchone()[0] == 0:
            cur.execute("""
                ALTER TABLE `cnic_data` 
                ADD COLUMN `document_id` VARCHAR(20) NOT NULL AFTER `id`
            """)
            print("  cnic_data.document_id added ✓")
        else:
            cur.execute("""
                ALTER TABLE `cnic_data` 
                MODIFY COLUMN `document_id` VARCHAR(20) NOT NULL
            """)
            print("  cnic_data.document_id already exists, altered to VARCHAR(20) ✓")

        # ── Step 5: Recreate all FK constraints ────────────────────────────
        print("\nStep 5: Recreating FK constraints...")
        
        ALL_CHILD_TABLES = NAF_TABLES + ["cnic_data"]
        for table in ALL_CHILD_TABLES:
            fk_name = f"{table}_ibfk_doc"
            cur.execute(f"""
                ALTER TABLE `{table}` 
                ADD CONSTRAINT `{fk_name}` 
                FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) 
                ON DELETE CASCADE
            """)
            print(f"  {table} → documents(id) FK ✓")

        conn.commit()
        print("\n✅ Migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run_migration()
