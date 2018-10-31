DROP TABLE IF EXISTS episode;
DROP TABLE IF EXISTS snapshot;

CREATE TABLE episode (
    id           INTEGER PRIMARY KEY,
    episode_slug TEXT    NOT NULL,
    season_slug  TEXT    NOT NULL
);
CREATE TABLE snapshot (
    episode_id INTEGER,
    ms         INTEGER,
    full_jpeg  BLOB    NOT NULL,
    tiny_jpeg  BLOB    NOT NULL,
               PRIMARY KEY (episode_id, ms)
               FOREIGN KEY (episode_id) REFERENCES episode(id)
               CHECK(ms >= 0)
);
