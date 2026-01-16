"""
Test script for movie answer validation

Run this to test if movie answer checking works correctly.
Usage: python test_movie_validation.py
"""

from answer_handler import AnswerHandler

def test_movie_answers():
    """Test movie title matching with various inputs"""

    test_cases = [
        # (user_answer, movie_title, should_match)
        ("The Matrix", "The Matrix", True),
        ("the matrix", "The Matrix", True),
        ("Matrix", "The Matrix", True),  # Article removed
        ("The Matrix (1999)", "The Matrix", True),  # With year
        ("matrix", "The Matrix", True),
        ("The Matrixx", "The Matrix", False),  # Typo
        ("Matrix Reloaded", "The Matrix", False),  # Different movie
        ("Inception", "The Matrix", False),
        ("Die Hard", "Die Hard", True),
        ("Diehard", "Die Hard", True),  # Space removed
        ("die hard", "Die Hard", True),
    ]

    print("Testing Movie Answer Validation\n")
    print("=" * 60)

    for user_input, correct_title, should_match in test_cases:
        # Normalize user input (simulating what happens in submit_answer)
        normalized_input = AnswerHandler.normalize_answer(user_input)

        # Check if it matches
        is_correct, similarity = AnswerHandler.check_movie_answer(
            normalized_input,
            correct_title
        )

        # Determine result
        passed = is_correct == should_match
        status = "✓ PASS" if passed else "✗ FAIL"

        print(f"{status} | User: '{user_input}' vs '{correct_title}'")
        print(f"      | Normalized: '{normalized_input}' | Match: {is_correct} | Similarity: {similarity:.1f}%")

        if not passed:
            print(f"      | Expected: {should_match}, Got: {is_correct}")
        print()

    print("=" * 60)

if __name__ == "__main__":
    test_movie_answers()
