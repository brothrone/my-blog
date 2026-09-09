CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  thread TEXT NOT NULL,
  name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 40),
  body TEXT NOT NULL CHECK(length(body) BETWEEN 1 AND 2000),
  created_at INTEGER NOT NULL,
  delete_hash TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'published' CHECK(status IN ('published','hidden'))
);
CREATE INDEX IF NOT EXISTS comments_thread ON comments(thread, status, id DESC);
CREATE TABLE IF NOT EXISTS comment_limits (
  bucket TEXT PRIMARY KEY,
  count INTEGER NOT NULL,
  last_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS comment_limits_expiry ON comment_limits(expires_at);
CREATE TABLE IF NOT EXISTS comment_replies (
  comment_id INTEGER PRIMARY KEY REFERENCES comments(id) ON DELETE CASCADE,
  body TEXT NOT NULL CHECK(length(body) BETWEEN 1 AND 2000),
  created_at INTEGER NOT NULL
);
