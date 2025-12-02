"""Generate test data for crosswords analytics."""

import random
import uuid
from datetime import datetime, timedelta

import psycopg2
from psycopg2.extras import execute_values

# Database connection
DB_URL = "postgresql://crossword:crosswords_password@localhost:5432/crossword_db"


def generate_submissions(grid_id: int, num_submissions: int = 50):
    """Generate realistic test submissions for a grid."""
    submissions = []

    for i in range(num_submissions):
        # Random completion metrics
        total_words = random.randint(10, 30)
        words_found = random.randint(int(total_words * 0.3), total_words)

        # Completion time (30 seconds to 2 hours)
        completion_time = random.randint(30, 7200)

        # Joker usage (30% chance)
        joker_used = random.random() < 0.3

        # Calculate scores
        correct_cells = random.randint(0, 200)
        base_score = correct_cells * 5.0

        # Time bonus (faster = better)
        time_bonus = max(0, (3600 - completion_time) / 10)

        # Joker penalty
        joker_penalty = 50.0 if joker_used else 0.0

        # Final score
        final_score = max(0, base_score + time_bonus - joker_penalty)

        # Submission date (last 30 days)
        days_ago = random.randint(0, 30)
        submitted_at = datetime.now() - timedelta(
            days=days_ago, hours=random.randint(0, 23)
        )

        submissions.append(
            {
                "id": str(uuid.uuid4()),
                "grid_id": grid_id,
                "correct_cells": correct_cells,
                "base_score": base_score,
                "time_bonus": time_bonus,
                "joker_penalty": joker_penalty,
                "final_score": final_score,
                "completion_time_seconds": completion_time,
                "words_found": words_found,
                "total_words": total_words,
                "joker_used": joker_used,
                "submitted_at": submitted_at,
            }
        )

    return submissions


def create_test_users(conn, num_users):
    """Create multiple test users."""
    cursor = conn.cursor()
    user_ids = []

    for i in range(num_users):
        user_id = str(uuid.uuid4())
        email = f"testuser{i}@example.com"
        pseudo = f"Player{i + 1}"

        cursor.execute(
            """
            INSERT INTO users (id, email, pseudo, roles, password, is_verified, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO NOTHING
            RETURNING id
        """,
            (
                user_id,
                email,
                pseudo,
                '["ROLE_USER"]',
                "$2y$13$hashedpassword",  # Dummy hashed password
                True,
                datetime.now(),
                datetime.now(),
            ),
        )

        result = cursor.fetchone()
        if result:
            user_ids.append(result[0])
        else:
            # User already exists, fetch it
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            user_ids.append(cursor.fetchone()[0])

    conn.commit()
    return user_ids


def insert_submissions(conn, submissions, user_ids):
    """Insert submissions into database."""
    cursor = conn.cursor()

    # Assign each submission to a different user
    values = [
        (
            sub["id"],
            user_ids[i % len(user_ids)],  # Cycle through users
            sub["grid_id"],
            sub["correct_cells"],
            sub["base_score"],
            sub["time_bonus"],
            sub["joker_penalty"],
            sub["final_score"],
            sub["completion_time_seconds"],
            sub["words_found"],
            sub["total_words"],
            sub["joker_used"],
            sub["submitted_at"],
        )
        for i, sub in enumerate(submissions)
    ]

    execute_values(
        cursor,
        """
        INSERT INTO submission (
            id, user_id, grid_id, correct_cells, base_score, time_bonus,
            joker_penalty, final_score, completion_time_seconds,
            words_found, total_words, joker_used, submitted_at
        ) VALUES %s
        """,
        values,
    )

    conn.commit()
    print(f"✅ Inserted {len(submissions)} submissions")


def main():
    """Main function to generate test data."""
    print("🚀 Generating test data for Crosswords Analytics...")

    # Connect to database
    conn = psycopg2.connect(DB_URL)

    try:
        # Check available grids
        cursor = conn.cursor()
        cursor.execute("SELECT id, version FROM grids ORDER BY id LIMIT 5")
        grids = cursor.fetchall()

        if not grids:
            print("❌ No grids found in database!")
            return

        print(f"📊 Found {len(grids)} grids")

        # Generate submissions for each grid
        for grid_id, version in grids:
            print(f"\n📝 Generating data for Grid {grid_id} (version: {version})...")

            # Delete existing test submissions for this grid
            cursor.execute("DELETE FROM submission WHERE grid_id = %s", (grid_id,))
            conn.commit()

            # Generate submissions (2500 per grid for performance testing)
            num_submissions = 2500
            print(f"🎲 Generating {num_submissions} submissions...")
            submissions = generate_submissions(grid_id, num_submissions)

            # Create enough test users for these submissions
            print(f"👥 Creating {num_submissions} test users...")
            user_ids = create_test_users(conn, num_submissions)
            print(f"✅ Created {len(user_ids)} test users")

            # Insert submissions (in batches for better performance)
            print("💾 Inserting submissions...")
            insert_submissions(conn, submissions, user_ids)

        print("\n✨ Test data generation completed!")
        print("\n🎯 You can now view the analytics dashboard with realistic data!")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
