PRAGMA foreign_keys = ON;
DROP TABLE IF EXISTS snapshot;
DROP TABLE IF EXISTS snapshot_tiny;
DROP TABLE IF EXISTS episode;

CREATE TABLE episode (
    id           INTEGER PRIMARY KEY,
    season_slug  TEXT    NOT NULL,
    episode_slug TEXT    NOT NULL
);
CREATE TABLE snapshot (
    episode_id    INTEGER,
    ms            INTEGER,
    png           BLOB    NOT NULL,
                  PRIMARY KEY (episode_id, ms)
                  FOREIGN KEY (episode_id) REFERENCES episode(id)
                  CHECK(ms >= 0)
);
CREATE TABLE snapshot_tiny (
    episode_id    INTEGER,
    ms            INTEGER,
    jpeg          BLOB    NOT NULL,
                  PRIMARY KEY (episode_id, ms)
                  FOREIGN KEY (episode_id) REFERENCES episode(id)
                  CHECK(ms >= 0)
);
