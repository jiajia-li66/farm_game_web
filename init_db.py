#!/usr/bin/env python3
# init_db.py
"""
Farm‑Game database initialiser / migrator.

Usage
-----
    python init_db.py --reset --db ./farm_game.db
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Final

# ────────────────────────────────────────────────
#  SQL schema & seed data
# ────────────────────────────────────────────────

SCHEMA_SQL: Final[str] = r"""
PRAGMA foreign_keys = ON;

-- 1. User --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS User (
    UserID      INTEGER PRIMARY KEY AUTOINCREMENT,
    Username    TEXT    NOT NULL UNIQUE,
    Password    TEXT    NOT NULL,              -- stored as sha256|salt
    Role        TEXT    NOT NULL DEFAULT 'player'
                  CHECK (Role IN ('player','admin'))
);

-- 2. Player ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Player (
    PlayerID      INTEGER PRIMARY KEY AUTOINCREMENT,
    CurrentGold   INTEGER NOT NULL DEFAULT 0,
    UserID        INTEGER UNIQUE,
    FOREIGN KEY (UserID) REFERENCES User(UserID)
);

-- 3. Item --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Item (
    ItemID      INTEGER PRIMARY KEY AUTOINCREMENT,
    ItemName    TEXT    NOT NULL UNIQUE,
    ItemType    TEXT    NOT NULL,
    Description TEXT
);

-- 4. Plant -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Plant (
    PlantID              INTEGER PRIMARY KEY AUTOINCREMENT,
    PlantName            TEXT    NOT NULL UNIQUE,
    BaseGrowthTime       INTEGER NOT NULL,
    WaterEffectPerTime   INTEGER NOT NULL,
    MaxWaterTimes        INTEGER NOT NULL,
    SellPrice            INTEGER NOT NULL,
    HarvestYield         INTEGER NOT NULL DEFAULT 1
);

-- 5. Plot --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Plot (
    PlotID                INTEGER PRIMARY KEY AUTOINCREMENT,
    PlayerID              INTEGER NOT NULL,
    Status                TEXT    NOT NULL DEFAULT 'Empty',
    PlantedPlantID        INTEGER,
    CurrentGrowthTimeLeft INTEGER,
    TimesWatered          INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (PlayerID)      REFERENCES Player(PlayerID),
    FOREIGN KEY (PlantedPlantID) REFERENCES Plant(PlantID)
);

-- 6. Inventory ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Inventory (
    PlayerID  INTEGER NOT NULL,
    ItemID    INTEGER NOT NULL,
    Quantity  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (PlayerID, ItemID),
    FOREIGN KEY (PlayerID) REFERENCES Player(PlayerID),
    FOREIGN KEY (ItemID)   REFERENCES Item(ItemID)
);

-- 7. Villager ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Villager (
    VillagerID   INTEGER PRIMARY KEY AUTOINCREMENT,
    VillagerName TEXT NOT NULL,
    Gender       TEXT NOT NULL,
    Description  TEXT
);

-- 8. Affection ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Affection (
    PlayerID       INTEGER NOT NULL,
    VillagerID     INTEGER NOT NULL,
    AffectionLevel INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (PlayerID, VillagerID),
    FOREIGN KEY (PlayerID)   REFERENCES Player(PlayerID),
    FOREIGN KEY (VillagerID) REFERENCES Villager(VillagerID)
);

-- 9. VillagerOrder -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS VillagerOrder (
    OrderID          INTEGER PRIMARY KEY AUTOINCREMENT,
    VillagerID       INTEGER NOT NULL,
    RequiredItemID   INTEGER NOT NULL,
    RequiredQuantity INTEGER NOT NULL DEFAULT 1,
    RewardGold       INTEGER NOT NULL,
    RewardAffection  INTEGER NOT NULL DEFAULT 0,
    Status           TEXT    NOT NULL DEFAULT 'Available',
    PostedTime       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ExpiryTime       TEXT,
    FOREIGN KEY (VillagerID)     REFERENCES Villager(VillagerID),
    FOREIGN KEY (RequiredItemID) REFERENCES Item(ItemID)
);

-- 10. GoldTransaction --------------------------------------------------------
CREATE TABLE IF NOT EXISTS GoldTransaction (
    TransactionID   INTEGER PRIMARY KEY AUTOINCREMENT,
    PlayerID        INTEGER NOT NULL,
    Timestamp       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Type            TEXT    NOT NULL,
    Amount          INTEGER NOT NULL,
    SourceReference TEXT    NOT NULL,
    FOREIGN KEY (PlayerID) REFERENCES Player(PlayerID)
);

-- 11. ShopItem ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ShopItem (
    ItemID     INTEGER PRIMARY KEY,
    SellPrice  INTEGER NOT NULL,
    FOREIGN KEY (ItemID) REFERENCES Item(ItemID)
);
"""

SEED_SQL: Final[str] = r"""
-- Initial Items
INSERT OR IGNORE INTO Item (ItemName, ItemType, Description) VALUES
 ('萝卜种子', '种子', '用于种植萝卜'),
 ('萝卜',     '作物', '成熟后的萝卜'),
 ('小麦',     '作物', '成熟后的小麦'),
 ('小麦种子', '种子', '用于种植小麦'),
 ('水滴',     '材料', '用于浇水');

-- Plants
INSERT OR IGNORE INTO Plant
 (PlantName, BaseGrowthTime, WaterEffectPerTime, MaxWaterTimes, SellPrice, HarvestYield)
VALUES
 ('萝卜',  60, 10, 3, 15, 1),
 ('胡萝卜', 90, 15, 8, 20, 1),
 ('小麦',  70, 13, 6, 18, 1);

-- Villagers
INSERT OR IGNORE INTO Villager (VillagerName, Gender, Description)
VALUES
 ('小芳', '女', '热情的村花，希望有人帮她收集萝卜'),
 ('老张', '男', '经验丰富的农民，正在寻找小麦');

-- Villager Orders
INSERT OR IGNORE INTO VillagerOrder
 (VillagerID, RequiredItemID, RequiredQuantity, RewardGold, RewardAffection)
VALUES
 (1, (SELECT ItemID FROM Item WHERE ItemName='萝卜'), 5, 50, 5),
 (2, (SELECT ItemID FROM Item WHERE ItemName='小麦'), 3, 70, 8);

-- Shop Items
INSERT OR IGNORE INTO ShopItem
 SELECT ItemID, 5 FROM Item WHERE ItemName='萝卜种子'
 UNION ALL
 SELECT ItemID, 2 FROM Item WHERE ItemName='水滴';
"""

ADMIN_USER: Final[tuple[str, str, str]] = ("admin", "123", "admin")
PLAYER_USER: Final[tuple[str, str, str]] = ("player1", "123456", "player")

# ────────────────────────────────────────────────
#  Helpers
# ────────────────────────────────────────────────


def sha256_hash(password: str, salt: str) -> str:
    """Return hex‑encoded sha256|salt string."""
    digest = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{digest}|{salt}"


def insert_users(conn: sqlite3.Connection) -> None:
    """Insert demo users with salted hashes."""
    cur = conn.cursor()
    for username, pwd, role in (ADMIN_USER, PLAYER_USER):
        salt = hashlib.sha256(os.urandom(16)).hexdigest()[:8]
        cur.execute(
            """
            INSERT OR IGNORE INTO User (Username, Password, Role)
            VALUES (?, ?, ?)
            """,
            (username, sha256_hash(pwd, salt), role),
        )


def run_script(conn: sqlite3.Connection, script: str) -> None:
    """Execute multi‑statement SQL with rollback on failure."""
    try:
        conn.executescript(script)
    except sqlite3.Error as exc:
        conn.rollback()
        raise
    else:
        conn.commit()


def build_or_migrate(db_path: Path, reset: bool, dump_schema: bool) -> None:
    """Create or migrate the SQLite database."""
    if reset and db_path.exists():
        confirm = input(f"⚠ Delete existing database at {db_path}? [y/N] ").lower()
        if confirm != "y":
            print("Aborted.")
            sys.exit(0)
        db_path.unlink()
        logging.warning("Existing DB removed.")

    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    run_script(conn, SCHEMA_SQL)
    run_script(conn, SEED_SQL)
    insert_users(conn)
    conn.commit()
    conn.close()

    if dump_schema:
        schema_file = db_path.with_suffix(".schema.sql")
        schema_file.write_text(SCHEMA_SQL + "\n\n" + SEED_SQL, encoding="utf-8")
        logging.info("Schema dumped to %s", schema_file)

    logging.info("✅ Database ready at %s", db_path)


# ────────────────────────────────────────────────
#  CLI
# ────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    cfg_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    default_db = cfg_dir / "farm_game" / "farm_game.db"

    p = argparse.ArgumentParser(description="Initialise or migrate Farm‑Game DB.")
    p.add_argument("--db", type=Path, default=default_db, help="Path to SQLite DB file")
    p.add_argument("--reset", action="store_true", help="Drop & recreate database")
    p.add_argument("--dump-schema", action="store_true", help="Write schema SQL file")
    p.add_argument("--quiet", action="store_true", help="Suppress info logs")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s | %(message)s",
    )
    try:
        build_or_migrate(args.db, args.reset, args.dump_schema)
    except sqlite3.Error as e:
        logging.error("SQLite error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
