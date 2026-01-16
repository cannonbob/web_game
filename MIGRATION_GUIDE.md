# Answer Migration Guide

## Overview

This guide explains how to migrate answers from the `questions` table to the new `answers_expected` table.

## What the Script Does

The migration script (`migrate_answers.py`) will:

1. ✅ Read all questions that have answers in the `questions.answer` column
2. ✅ Create corresponding entries in `answers_expected` table
3. ✅ Normalize answers (lowercase, trimmed, remove extra spaces)
4. ✅ Detect input type (normal vs guess for numeric answers)
5. ✅ Generate hints automatically
6. ✅ Mark all migrated answers as primary (`is_primary = 1`)
7. ✅ Skip questions that already have entries in `answers_expected`
8. ✅ Preserve original answers in `answer_raw` column

## Migration Steps

### Step 1: Preview (Dry Run)

First, run the script in dry-run mode to see what will happen:

```bash
python migrate_answers.py
```

This will:
- Show you all questions that will be migrated
- Display the raw and normalized versions of each answer
- NOT make any changes to the database

**Review the output carefully!**

### Step 2: Run Migration (Live)

Once you're satisfied with the preview, run the actual migration:

```bash
python migrate_answers.py --live
```

You'll be prompted to confirm:
```
⚠️  This will modify the database. Continue? (yes/no):
```

Type `yes` and press Enter to proceed.

### Step 3: Verify

After migration, verify everything worked correctly:

```bash
python migrate_answers.py --verify
```

This will show:
- Number of questions with answers
- Number of entries in answers_expected
- Number of questions missing answers_expected entries

## What Gets Migrated

### Field Mapping

| Source (questions) | Destination (answers_expected) | Logic |
|-------------------|--------------------------------|-------|
| `id` | `question_id` | Direct FK reference |
| `answer` | `answer_raw` | Original answer unchanged |
| `answer` | `answer_normalized` | Lowercase, trimmed, cleaned |
| - | `input_type` | Auto-detected: 'guess' for numbers, 'normal' otherwise |
| `answer` | `hint` | First 50 chars or generic hint |
| - | `is_primary` | Always set to 1 |
| - | `rank` | Set to NULL |

### Normalization Logic

The script normalizes answers by:
- Converting to lowercase
- Removing leading/trailing whitespace
- Removing multiple spaces (replaced with single space)
- Removing leading/trailing punctuation (.,!?;:"\'-)

### Input Type Detection

- **'guess'**: If answer is numeric (e.g., "42", "3.14", "1,000")
- **'normal'**: All other answers (text, names, etc.)

## Example Output

```
✅ Question 15:
   Raw: The Great Gatsby
   Normalized: the great gatsby
   Input Type: normal
   Hint: The Great Gatsby
   ✔️  Inserted into answers_expected

✅ Question 23:
   Raw: 1984
   Normalized: 1984
   Input Type: guess
   Hint: Enter your answer
   ✔️  Inserted into answers_expected
```

## Safety Features

1. **Dry Run Default**: Script runs in preview mode by default
2. **Skip Duplicates**: Automatically skips questions that already have answers
3. **Error Handling**: Continues processing even if one question fails
4. **Rollback on Error**: Database changes rolled back if an error occurs
5. **Verification Tool**: Built-in verification to check migration success

## After Migration

Once migration is complete, you can:

1. **Add alternative answers** for existing questions:
   ```sql
   INSERT INTO answers_expected
   (question_id, input_type, hint, answer_raw, answer_normalized, is_primary)
   VALUES
   (15, 'normal', 'F. Scott Fitzgerald novel', 'Great Gatsby', 'great gatsby', 0);
   ```

2. **Update hints** if needed:
   ```sql
   UPDATE answers_expected
   SET hint = 'Famous 1925 novel'
   WHERE id = 42;
   ```

3. **Keep or remove** the old `questions.answer` column (your choice)

## Troubleshooting

### "Already has X answer(s) - SKIPPING"

This is normal! The script detected that answers already exist for this question, so it skips it to avoid duplicates.

### "ERROR processing question X"

Check the error message. Common causes:
- Answer too long (>255 chars for varchar fields)
- Database connection issues
- Foreign key constraint violations

### "Questions missing answers_expected"

Run the migration again:
```bash
python migrate_answers.py --live
```

The script will process only the missing questions.

## Rollback (If Needed)

If something goes wrong, you can rollback by deleting the migrated answers:

```sql
-- BE CAREFUL: This deletes ALL entries from answers_expected
DELETE FROM answers_expected;
```

Then run the migration again.

## Notes

- The original `questions.answer` column is NOT modified or deleted
- You can safely run the script multiple times (it skips duplicates)
- All migrated answers are marked as primary (`is_primary = 1`)
- The `rank` field is left as NULL (you can set it manually later if needed)
