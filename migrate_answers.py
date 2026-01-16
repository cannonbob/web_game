"""
Migration script to move answers from questions table to answers_expected table.

This script:
1. Reads all questions with their answers
2. Creates corresponding entries in answers_expected table
3. Normalizes answers (lowercase, trimmed, etc.)
4. Sets appropriate input_type based on question characteristics
"""

from app import app
from db import db
from models.game import Question
import re

def normalize_answer(answer):
    """
    Normalize an answer for comparison.
    - Convert to lowercase
    - Remove extra whitespace
    - Remove special characters (except letters, numbers, spaces)
    """
    if not answer:
        return ''

    # Convert to lowercase
    normalized = answer.lower().strip()

    # Remove multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized)

    # Remove leading/trailing punctuation
    normalized = normalized.strip('.,!?;:"\'-')

    return normalized

def determine_input_type(question):
    """
    Determine the input_type based on question characteristics.
    Returns: 'normal', 'guess', or other custom types
    """
    # Check if it's a numeric answer (for guess-type questions)
    if question.answer and question.answer.replace('.', '', 1).replace(',', '').isdigit():
        return 'guess'

    # Default to normal
    return 'normal'

def create_hint(answer):
    """
    Create a hint from the answer.
    Uses first 50 characters or full answer if shorter.
    """
    if not answer:
        return 'Enter your answer'

    # For short answers, use a generic hint
    if len(answer) <= 3:
        return 'Enter your answer'

    # For longer answers, truncate to 50 chars
    if len(answer) > 50:
        return answer[:47] + '...'

    return answer

def migrate_answers(dry_run=True):
    """
    Migrate answers from questions table to answers_expected table.

    Args:
        dry_run: If True, only prints what would be done without making changes
    """
    print("=" * 80)
    print("ANSWER MIGRATION SCRIPT")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (making changes)'}")
    print()

    with app.app_context():
        # Get all questions with answers
        questions = Question.query.filter(Question.answer != '').filter(Question.answer != None).all()

        print(f"Found {len(questions)} questions with answers")
        print()

        migrated_count = 0
        skipped_count = 0
        error_count = 0

        for question in questions:
            try:
                # Check if answer already exists in answers_expected
                existing = db.session.execute(
                    db.text("SELECT COUNT(*) FROM answers_expected WHERE question_id = :qid"),
                    {"qid": question.id}
                ).scalar()

                if existing > 0:
                    print(f"⏭️  Question {question.id}: Already has {existing} answer(s) - SKIPPING")
                    skipped_count += 1
                    continue

                # Prepare answer data
                answer_raw = question.answer
                answer_normalized = normalize_answer(answer_raw)
                input_type = determine_input_type(question)
                hint = create_hint(answer_raw)

                print(f"✅ Question {question.id}:")
                print(f"   Raw: {answer_raw[:60]}{'...' if len(answer_raw) > 60 else ''}")
                print(f"   Normalized: {answer_normalized[:60]}{'...' if len(answer_normalized) > 60 else ''}")
                print(f"   Input Type: {input_type}")
                print(f"   Hint: {hint}")

                if not dry_run:
                    # Insert into answers_expected
                    # Note: rank is a reserved keyword in MySQL, so we escape it with backticks
                    db.session.execute(
                        db.text("""
                            INSERT INTO answers_expected
                            (question_id, input_type, hint, answer_raw, answer_normalized, is_primary, `rank`)
                            VALUES
                            (:question_id, :input_type, :hint, :answer_raw, :answer_normalized, :is_primary, :rank)
                        """),
                        {
                            "question_id": question.id,
                            "input_type": input_type,
                            "hint": hint,
                            "answer_raw": answer_raw,
                            "answer_normalized": answer_normalized,
                            "is_primary": 1,
                            "rank": None
                        }
                    )
                    db.session.commit()
                    print(f"   ✔️  Inserted into answers_expected")
                else:
                    print(f"   ℹ️  Would insert into answers_expected (DRY RUN)")

                print()
                migrated_count += 1

            except Exception as e:
                print(f"❌ ERROR processing question {question.id}: {e}")
                print()
                error_count += 1
                if not dry_run:
                    db.session.rollback()

        print("=" * 80)
        print("MIGRATION SUMMARY")
        print("=" * 80)
        print(f"Total questions processed: {len(questions)}")
        print(f"Successfully migrated: {migrated_count}")
        print(f"Skipped (already exist): {skipped_count}")
        print(f"Errors: {error_count}")
        print()

        if dry_run:
            print("⚠️  DRY RUN MODE - No changes were made to the database")
            print("   Run with dry_run=False to apply changes")
        else:
            print("✅ LIVE MODE - Changes have been committed to the database")

        print("=" * 80)

def verify_migration():
    """
    Verify the migration by comparing counts and checking data integrity.
    """
    print("=" * 80)
    print("VERIFICATION")
    print("=" * 80)

    with app.app_context():
        # Count questions with answers
        questions_count = db.session.execute(
            db.text("SELECT COUNT(*) FROM questions WHERE answer IS NOT NULL AND answer != ''")
        ).scalar()

        # Count answers_expected entries
        answers_count = db.session.execute(
            db.text("SELECT COUNT(*) FROM answers_expected")
        ).scalar()

        # Count questions without answers_expected entries
        missing_count = db.session.execute(
            db.text("""
                SELECT COUNT(*) FROM questions q
                WHERE q.answer IS NOT NULL AND q.answer != ''
                AND NOT EXISTS (
                    SELECT 1 FROM answers_expected ae WHERE ae.question_id = q.id
                )
            """)
        ).scalar()

        print(f"Questions with answers: {questions_count}")
        print(f"Entries in answers_expected: {answers_count}")
        print(f"Questions missing answers_expected: {missing_count}")
        print()

        if missing_count == 0:
            print("✅ All questions have corresponding answers_expected entries!")
        else:
            print(f"⚠️  {missing_count} questions are missing answers_expected entries")
            print("   Run the migration again to complete")

        print("=" * 80)

if __name__ == "__main__":
    import sys

    print()
    print("Answer Migration Script")
    print("=" * 80)
    print()
    print("This script will migrate answers from the questions table")
    print("to the answers_expected table.")
    print()
    print("Options:")
    print("  python migrate_answers.py                 - Run in DRY RUN mode (preview only)")
    print("  python migrate_answers.py --live           - Run in LIVE mode (make changes)")
    print("  python migrate_answers.py --verify         - Verify migration status")
    print()

    if len(sys.argv) > 1:
        if sys.argv[1] == '--live':
            response = input("⚠️  This will modify the database. Continue? (yes/no): ")
            if response.lower() == 'yes':
                migrate_answers(dry_run=False)
                print()
                verify_migration()
            else:
                print("Migration cancelled.")
        elif sys.argv[1] == '--verify':
            verify_migration()
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --live to run migration or --verify to check status")
    else:
        # Default: dry run
        migrate_answers(dry_run=True)
        print()
        print("To apply these changes, run:")
        print("  python migrate_answers.py --live")
