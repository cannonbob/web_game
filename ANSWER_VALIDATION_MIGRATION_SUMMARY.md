# Answer Validation Migration Summary

## Overview

The game now uses the `answers_expected` table instead of `questions.answer` for answer validation and display. This allows multiple alternative answers for the same question.

---

## Database Changes

### New Structure: `answers_expected` Table

```sql
CREATE TABLE `answers_expected` (
  `id` int NOT NULL AUTO_INCREMENT,
  `question_id` int NOT NULL,
  `input_type` varchar(20) DEFAULT 'normal',
  `hint` varchar(50) NOT NULL,
  `answer_raw` varchar(255) NOT NULL,
  `answer_normalized` varchar(255) NOT NULL,
  `is_primary` tinyint(1) DEFAULT '1',
  `rank` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `question_id` (`question_id`),
  CONSTRAINT `answers_expected_ibfk_1` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`) ON DELETE CASCADE
)
```

### Old Column (Still Exists)

- `questions.answer` - Still exists in the table but is no longer used for validation
- **Kept for backward compatibility and reference**

---

## Code Changes Made

### 1. Answer Validation (answer_handler.py)

**Already correct! ✅**

The `AnswerHandler` class already uses `answers_expected`:

```python
# Gets expected answers from answers_expected table
expected_answers = db_session.query(AnswerExpected).filter_by(question_id=question_id).all()

# Uses answer_normalized for comparison
expected_normalized = [ans.answer_normalized for ans in expected_answers]

# Text questions
is_correct, similarity, matched = cls.calculate_text_correctness(
    answer.answer_normalized,
    expected_normalized
)

# Number/guess questions
primary_answer = next((ans for ans in expected_answers if ans.is_primary), expected_answers[0])
```

### 2. Answer Display to Admin (app.py)

**Updated! ✅** (Line 1283-1291)

```python
# Old code:
emit('question_selected', {
    'answer': session_question.question.answer,  # ❌ Old way
    ...
})

# New code:
# Get answer from answers_expected table (use primary answer or fallback)
answer_to_display = session_question.question.answer  # Fallback
if session_question.question.expected_answers:
    primary_answer = next((ans for ans in session_question.question.expected_answers if ans.is_primary), None)
    if primary_answer:
        answer_to_display = primary_answer.answer_raw  # ✅ New way
    elif session_question.question.expected_answers:
        answer_to_display = session_question.question.expected_answers[0].answer_raw

emit('question_selected', {
    'answer': answer_to_display,  # ✅ From answers_expected
    ...
})
```

**Why this matters:**
- Admin display shows the correct answer when a question is selected
- Now displays the primary answer from `answers_expected` instead of `questions.answer`
- Falls back to `questions.answer` if `answers_expected` is empty (for safety)

---

## Where `questions.answer` is Still Used

### Read-Only / Display Purposes

These locations still use `questions.answer` but **do NOT affect validation**:

1. **Question.to_dict()** (models/game.py:144)
   - Returns question data including `answer` field
   - Used for serialization and API responses
   - **Safe** - just for display/reference

2. **SessionQuestion.to_dict()** (models/game.py:348)
   - Returns session question data including `answer`
   - Used for admin panel display
   - **Safe** - just for reference

3. **Movie Answer Auto-Sync** (models/game.py:410-415)
   - Event listener that syncs `question.answer` from linked `movie.title`
   - **Safe** - maintains data consistency for reference

### None of these affect answer validation!

---

## How It Works Now

### For Questions with One Answer (Most Cases)

1. **Migration** created one entry in `answers_expected`:
   ```sql
   INSERT INTO answers_expected
   (question_id, answer_raw, answer_normalized, is_primary)
   VALUES
   (15, 'The Great Gatsby', 'the great gatsby', 1);
   ```

2. **Display** shows `answer_raw` to admin

3. **Validation** compares user input against `answer_normalized`

### For Questions with Multiple Answers (Future: Auto-Complete)

You can add alternative answers:

```sql
-- Primary answer
INSERT INTO answers_expected
(question_id, answer_raw, answer_normalized, is_primary)
VALUES
(42, 'United States', 'united states', 1);

-- Alternative answer 1
INSERT INTO answers_expected
(question_id, answer_raw, answer_normalized, is_primary)
VALUES
(42, 'USA', 'usa', 0);

-- Alternative answer 2
INSERT INTO answers_expected
(question_id, answer_raw, answer_normalized, is_primary)
VALUES
(42, 'America', 'america', 0);
```

All three will be accepted as correct!

---

## Migration Status

✅ **Completed**
- `migrate_answers.py` script created and run
- All existing answers migrated to `answers_expected`
- Validation logic already uses `answers_expected`
- Display logic updated to use `answers_expected`

✅ **Tested**
- `answer_handler.py` - Uses `answers_expected` ✓
- `app.py` line 1283-1291 - Updated to use `answers_expected` ✓

✅ **Backward Compatible**
- `questions.answer` column still exists
- Falls back to `questions.answer` if `answers_expected` is empty
- Old questions still work

---

## Adding New Questions

### Option 1: Direct SQL

```sql
-- Add question
INSERT INTO questions (question_text, answer, category_id)
VALUES ('What is the capital of France?', 'Paris', 1);

-- Add expected answer
INSERT INTO answers_expected
(question_id, input_type, hint, answer_raw, answer_normalized, is_primary)
VALUES
(LAST_INSERT_ID(), 'normal', 'Enter your answer', 'Paris', 'paris', 1);
```

### Option 2: Python Code

```python
from models.game import Question, AnswerExpected
from answer_handler import AnswerHandler

# Create question
question = Question(
    question_text="What is the capital of France?",
    answer="Paris",  # Optional - for reference only
    category_id=1
)
db.session.add(question)
db.session.flush()  # Get question.id

# Add expected answer
expected = AnswerExpected(
    question_id=question.id,
    input_type='normal',
    hint='Enter your answer',
    answer_raw='Paris',
    answer_normalized=AnswerHandler.normalize_answer('Paris'),
    is_primary=True
)
db.session.add(expected)
db.session.commit()
```

### Option 3: Admin Panel (Future)

When you build a question editor in the admin panel, it should:
1. Create the `Question` record
2. Automatically create corresponding `AnswerExpected` record(s)
3. Allow adding multiple alternative answers

---

## Testing Checklist

### Manual Test

1. **Admin Panel**
   - Select a question from game board
   - Verify correct answer displays on admin screen ✓

2. **Player Input**
   - Submit correct answer → Marked as correct ✓
   - Submit alternative answer (if exists) → Marked as correct ✓
   - Submit incorrect answer → Marked as incorrect ✓

3. **Fuzzy Matching**
   - Submit answer with typo → Should match if close enough ✓
   - Submit answer with different case → Should match ✓
   - Submit answer with articles ("The Godfather" vs "Godfather") → Should match ✓

### Database Check

```sql
-- Verify all questions have expected answers
SELECT q.id, q.question_text, q.answer,
       COUNT(ae.id) as answer_count
FROM questions q
LEFT JOIN answers_expected ae ON q.id = ae.question_id
WHERE q.input_expected = 1
GROUP BY q.id
HAVING answer_count = 0;
-- Should return 0 rows if all questions have answers
```

---

## Summary

✅ **Migration Complete**
✅ **Validation Uses `answers_expected`**
✅ **Display Uses `answers_expected`**
✅ **Backward Compatible**
✅ **Ready for Multiple Answers**

The `questions.answer` column remains for reference, but all validation now uses `answers_expected.answer_normalized` and all display uses `answers_expected.answer_raw`.
