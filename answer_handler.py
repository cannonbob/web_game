"""
Answer Handler for Input Questions

Handles normalization, fuzzy matching, and correctness calculation
for user-submitted answers to quiz questions.
"""

import re
import string
from typing import List, Dict, Tuple, Optional

try:
    from rapidfuzz import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    print("Warning: rapidfuzz not installed. Install with: pip install rapidfuzz")


class AnswerHandler:
    """Handles answer normalization and correctness evaluation."""

    # Articles to remove (German and English)
    ARTICLES = {
        'der', 'die', 'das', 'den', 'dem', 'des',
        'ein', 'eine', 'einen', 'einem', 'eines', 'einer',
        'the', 'a', 'an'
    }

    # Umlaut replacements
    UMLAUT_MAP = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        'ß': 'ss'
    }

    # Fuzzy match threshold (0-100%)
    FUZZY_THRESHOLD = 90

    @classmethod
    def normalize_answer(cls, answer: str) -> str:
        """
        Normalize an answer string through a series of transformations:
        1. Convert to lowercase
        2. Trim whitespace
        3. Remove punctuation
        4. Reform umlauts (ä→ae, ö→oe, ü→ue, ß→ss)
        5. Remove articles (der, die, das, the, a, an, etc.)

        Args:
            answer: Raw answer string

        Returns:
            Normalized answer string
        """
        if not answer:
            return ''

        # Step 1: Convert to lowercase
        text = answer.lower()

        # Step 2: Trim whitespace
        text = text.strip()

        # Step 3: Remove punctuation
        text = text.translate(str.maketrans('', '', string.punctuation))

        # Step 4: Reform umlauts
        for umlaut, replacement in cls.UMLAUT_MAP.items():
            text = text.replace(umlaut.lower(), replacement)

        # Step 5: Remove articles
        words = text.split()
        words = [word for word in words if word not in cls.ARTICLES]
        text = ''.join(words)  # Join without spaces for stricter matching

        # Final trim (remove any remaining whitespace)
        text = text.strip()

        return text

    @classmethod
    def calculate_text_correctness(cls, user_answer: str, expected_answers: List[str],
                                   use_fuzzy: bool = True) -> Tuple[bool, float, Optional[str]]:
        """
        Calculate if a text answer is correct using exact match or fuzzy matching.

        Args:
            user_answer: Normalized user answer
            expected_answers: List of normalized expected answers
            use_fuzzy: Whether to use fuzzy matching (default: True)

        Returns:
            Tuple of (is_correct, similarity_score, matched_answer)
            - is_correct: Boolean indicating if answer is correct
            - similarity_score: Similarity score (0-100)
            - matched_answer: The expected answer that matched (or None)
        """
        if not user_answer or not expected_answers:
            return False, 0.0, None

        best_score = 0.0
        matched_answer = None

        for expected in expected_answers:
            # Exact match check
            if user_answer == expected:
                return True, 100.0, expected

            # Fuzzy match check
            if use_fuzzy and FUZZY_AVAILABLE:
                # Use token_sort_ratio to handle word order differences
                score = fuzz.token_sort_ratio(user_answer, expected)

                if score > best_score:
                    best_score = score
                    matched_answer = expected

        # Determine if answer is correct based on threshold
        is_correct = best_score >= cls.FUZZY_THRESHOLD

        return is_correct, best_score, matched_answer if is_correct else None

    @classmethod
    def calculate_number_distance(cls, user_answer: str, expected_answer: str) -> Tuple[bool, float, float]:
        """
        Calculate the distance between a guessed number and the correct answer.

        Args:
            user_answer: User's guess (as string)
            expected_answer: Correct answer (as string)

        Returns:
            Tuple of (is_exact, distance, user_number)
            - is_exact: Boolean indicating if guess is exact
            - distance: Absolute distance from correct answer
            - user_number: The parsed user number (for sorting)
        """
        try:
            # Parse numbers (handle both integer and float)
            user_num = float(user_answer.replace(',', '.'))
            expected_num = float(expected_answer.replace(',', '.'))

            # Calculate absolute distance
            distance = abs(user_num - expected_num)

            # Check if exact match
            is_exact = distance == 0

            return is_exact, distance, user_num

        except (ValueError, AttributeError):
            # If parsing fails, return invalid result
            return False, float('inf'), 0.0

    @classmethod
    def rank_number_guesses(cls, user_answers: List[Dict], expected_answer: str) -> List[Dict]:
        """
        Rank all user guesses by distance to correct answer.

        Args:
            user_answers: List of dicts with 'user_id', 'answer_raw', 'answer_normalized'
            expected_answer: The correct answer (as string)

        Returns:
            List of dicts with added 'distance', 'rank', 'is_winner' fields, sorted by distance
        """
        results = []

        for answer_data in user_answers:
            is_exact, distance, user_num = cls.calculate_number_distance(
                answer_data['answer_normalized'],
                expected_answer
            )

            results.append({
                **answer_data,
                'user_number': user_num,
                'distance': distance,
                'is_exact': is_exact
            })

        # Sort by distance (closest first)
        results.sort(key=lambda x: x['distance'])

        # Assign ranks and determine winners
        if results:
            min_distance = results[0]['distance']

            for i, result in enumerate(results, 1):
                result['rank'] = i
                # All users with the minimum distance are winners
                result['is_winner'] = (result['distance'] == min_distance)

        return results

    @classmethod
    def check_movie_answer(cls, user_answer: str, movie_title: str) -> Tuple[bool, float]:
        """
        Check if a user's answer matches a movie title.

        Args:
            user_answer: User's submitted answer (already normalized)
            movie_title: The correct movie title

        Returns:
            Tuple of (is_correct, similarity_score)
        """
        if not user_answer or not movie_title:
            return False, 0.0

        # Normalize the movie title
        normalized_title = cls.normalize_answer(movie_title)

        # Check exact match
        if user_answer == normalized_title:
            return True, 100.0

        # Check fuzzy match
        if FUZZY_AVAILABLE:
            score = fuzz.token_sort_ratio(user_answer, normalized_title)
            is_correct = score >= cls.FUZZY_THRESHOLD
            return is_correct, score

        return False, 0.0

    @classmethod
    def evaluate_movie_answers(cls, question_id: int, db_session) -> Dict:
        """
        Evaluate all user answers for a movie question.

        Args:
            question_id: Question ID to evaluate
            db_session: SQLAlchemy database session

        Returns:
            Dict with evaluation results and statistics
        """
        from models.game import Question, AnswerUser, Movie

        # Get question and verify it has a movie
        question = db_session.query(Question).filter_by(id=question_id).first()
        if not question or not question.movie_id:
            return {'error': 'Question not found or is not a movie question'}

        # Get the movie
        movie = db_session.query(Movie).filter_by(id=question.movie_id).first()
        if not movie:
            return {'error': 'Movie not found'}

        # Get all user answers for this question
        user_answers = db_session.query(AnswerUser).filter_by(question_id=question_id).all()

        results = {
            'question_id': question_id,
            'input_type': 'movie',  # Add input_type for consistency
            'movie_title': movie.title,
            'movie_year': movie.year,
            'total_submissions': len(user_answers),
            'user_results': []
        }

        correct_count = 0

        # Movie answers are already validated on submission (using movie ID comparison)
        # Just collect existing results, DO NOT re-evaluate
        for answer in user_answers:
            # Use the is_correct value that was set during submission
            is_correct = answer.is_correct

            if is_correct:
                correct_count += 1

            results['user_results'].append({
                'user_id': answer.user_id,
                'round': answer.round,
                'answer_raw': answer.answer_raw,
                'is_correct': is_correct,
                'similarity': 100.0 if is_correct else 0.0  # Dummy similarity for compatibility
            })

        # No need to commit - we're not changing anything

        # Calculate statistics
        results['correct_count'] = correct_count
        results['accuracy'] = (correct_count / len(user_answers) * 100) if user_answers else 0

        return results

    @classmethod
    def evaluate_all_answers(cls, question_id: int, db_session) -> Dict:
        """
        Evaluate all user answers for a specific question.

        Args:
            question_id: Question ID to evaluate
            db_session: SQLAlchemy database session

        Returns:
            Dict with evaluation results and statistics
        """
        from models.game import Question, AnswerExpected, AnswerUser

        # Get question
        question = db_session.query(Question).filter_by(id=question_id).first()
        if not question or not question.input_expected:
            return {'error': 'Question not found or does not expect input'}

        # Check if this is a movie question
        if question.movie_id:
            return cls.evaluate_movie_answers(question_id, db_session)

        # For non-movie questions, get expected answers
        expected_answers = db_session.query(AnswerExpected).filter_by(question_id=question_id).all()
        if not expected_answers:
            return {'error': 'No expected answers configured'}

        # Get all user answers
        user_answers = db_session.query(AnswerUser).filter_by(question_id=question_id).all()

        # Determine question type from first expected answer
        input_type = expected_answers[0].input_type

        results = {
            'question_id': question_id,
            'input_type': input_type,
            'total_submissions': len(user_answers),
            'user_results': []
        }

        if input_type == 'guess':
            # Number guessing question
            primary_answer = next((ans for ans in expected_answers if ans.is_primary), expected_answers[0])

            answer_data = [
                {
                    'user_id': ans.user_id,
                    'answer_id': ans.id,
                    'answer_raw': ans.answer_raw,
                    'answer_normalized': ans.answer_normalized
                }
                for ans in user_answers
            ]

            ranked_results = cls.rank_number_guesses(answer_data, primary_answer.answer_normalized)

            # Update results and database
            for result in ranked_results:
                # Update database
                answer = db_session.query(AnswerUser).filter_by(id=result['answer_id']).first()
                if answer:
                    answer.is_correct = result['is_winner']

                results['user_results'].append({
                    'user_id': result['user_id'],
                    'answer_raw': result['answer_raw'],
                    'guess': result['user_number'],
                    'distance': result['distance'],
                    'rank': result['rank'],
                    'is_winner': result['is_winner']
                })

            results['correct_answer'] = float(primary_answer.answer_normalized)

        else:
            # Normal text question
            expected_normalized = [ans.answer_normalized for ans in expected_answers]

            for answer in user_answers:
                is_correct, similarity, matched = cls.calculate_text_correctness(
                    answer.answer_normalized,
                    expected_normalized
                )

                # Update database
                answer.is_correct = is_correct

                results['user_results'].append({
                    'user_id': answer.user_id,
                    'answer_raw': answer.answer_raw,
                    'answer_normalized': answer.answer_normalized,
                    'is_correct': is_correct,
                    'similarity': similarity,
                    'matched_answer': matched
                })

            results['expected_answers'] = [ans.answer_raw for ans in expected_answers]

        # Commit changes
        db_session.commit()

        # Calculate statistics
        if input_type == 'guess':
            results['winners'] = [r for r in results['user_results'] if r['is_winner']]
            results['winner_count'] = len(results['winners'])
        else:
            results['correct_count'] = sum(1 for r in results['user_results'] if r['is_correct'])
            results['accuracy'] = (results['correct_count'] / results['total_submissions'] * 100) if results['total_submissions'] > 0 else 0

        return results
