PRAGMA foreign_keys = ON;

CREATE TABLE season (
    id       INTEGER PRIMARY KEY,
    slug     TEXT    NOT NULL,
    icon_png BLOB,
    name     TEXT
);
CREATE TABLE episode (
    id          INTEGER PRIMARY KEY,
    slug        TEXT    NOT NULL,
    name        TEXT,
    duration    INTEGER NOT NULL,
    snapshot_ms INTEGER,
    season_id   INTEGER NOT NULL,
                FOREIGN KEY (season_id) REFERENCES season(id)
);
CREATE TABLE snapshot (
    episode_id INTEGER NOT NULL,
    ms         INTEGER NOT NULL,
    png        BLOB    NOT NULL,
               PRIMARY KEY (episode_id, ms)
               FOREIGN KEY (episode_id) REFERENCES episode(id)
               CHECK(ms >= 0)
);
CREATE TABLE snapshot_tiny (
    episode_id INTEGER NOT NULL,
    ms         INTEGER NOT NULL,
    jpeg       BLOB    NOT NULL,
               PRIMARY KEY (episode_id, ms)
               FOREIGN KEY (episode_id) REFERENCES episode(id)
               CHECK(ms >= 0)
);
CREATE TABLE subtitle (
    episode_id  INTEGER NOT NULL,
    idx         INTEGER,
    start_ms    INTEGER NOT NULL,
    end_ms      INTEGER NOT NULL,
    snapshot_ms INTEGER,
    content     TEXT    NOT NULL,
                PRIMARY KEY (episode_id, idx)
                FOREIGN KEY (episode_id) REFERENCES episode(id)
                CHECK(start_ms >= 0)
                CHECK(end_ms > start_ms)
                CHECK(snapshot_ms >= start_ms)
                CHECK(snapshot_ms <= end_ms)
);
CREATE VIRTUAL TABLE subtitle_search
       USING fts5(episode_id UNINDEXED, snapshot_ms UNINDEXED, content,
                  tokenize = 'porter ascii');
