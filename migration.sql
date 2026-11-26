-- Run this once in the Neon SQL Editor before starting the updated Flask app.
-- It preserves existing tasks; old tasks remain unassigned (user_id = NULL).

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL
);

ALTER TABLE task
    ADD COLUMN IF NOT EXISTS user_id INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_name = 'tasks_user_id_fkey'
          AND table_name = 'task'
    ) THEN
        ALTER TABLE task
            ADD CONSTRAINT tasks_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES users(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_tasks_user_id ON task(user_id);
CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);
