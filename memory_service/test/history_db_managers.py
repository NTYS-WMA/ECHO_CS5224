#!/usr/bin/env python3
"""
Mem0历史数据库管理器
支持SQLite、PostgreSQL和MySQL
"""

import logging
import threading
import uuid
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
import os

logger = logging.getLogger(__name__)


class BaseHistoryManager(ABC):
    """历史数据库管理器基类"""

    @abstractmethod
    def add_history(
        self,
        memory_id: str,
        old_memory: Optional[str],
        new_memory: Optional[str],
        event: str,
        *,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        is_deleted: int = 0,
        actor_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        pass

    @abstractmethod
    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def reset(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class SQLiteHistoryManager(BaseHistoryManager):
    """SQLite历史数据库管理器（原版）"""

    def __init__(self, db_path: str = ":memory:"):
        import sqlite3

        self.db_path = db_path
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._migrate_history_table()
        self._create_history_table()

    def _migrate_history_table(self) -> None:
        """迁移历史表（与原版相同）"""
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                cur = self.connection.cursor()

                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='history'")
                if cur.fetchone() is None:
                    self.connection.execute("COMMIT")
                    return

                cur.execute("PRAGMA table_info(history)")
                old_cols = {row[1] for row in cur.fetchall()}

                expected_cols = {
                    "id", "memory_id", "old_memory", "new_memory", "event",
                    "created_at", "updated_at", "is_deleted", "actor_id", "role",
                }

                if old_cols == expected_cols:
                    self.connection.execute("COMMIT")
                    return

                logger.info("Migrating history table to new schema.")

                cur.execute("DROP TABLE IF EXISTS history_old")
                cur.execute("ALTER TABLE history RENAME TO history_old")

                cur.execute("""
                    CREATE TABLE history (
                        id           TEXT PRIMARY KEY,
                        memory_id    TEXT,
                        old_memory   TEXT,
                        new_memory   TEXT,
                        event        TEXT,
                        created_at   DATETIME,
                        updated_at   DATETIME,
                        is_deleted   INTEGER,
                        actor_id     TEXT,
                        role         TEXT
                    )
                """)

                intersecting = list(expected_cols & old_cols)
                if intersecting:
                    cols_csv = ", ".join(intersecting)
                    cur.execute(f"INSERT INTO history ({cols_csv}) SELECT {cols_csv} FROM history_old")

                cur.execute("DROP TABLE history_old")
                self.connection.execute("COMMIT")
                logger.info("History table migration completed successfully.")

            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"History table migration failed: {e}")
                raise

    def _create_history_table(self) -> None:
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id           TEXT PRIMARY KEY,
                        memory_id    TEXT,
                        old_memory   TEXT,
                        new_memory   TEXT,
                        event        TEXT,
                        created_at   DATETIME,
                        updated_at   DATETIME,
                        is_deleted   INTEGER,
                        actor_id     TEXT,
                        role         TEXT
                    )
                """)
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to create history table: {e}")
                raise

    def add_history(self, memory_id: str, old_memory: Optional[str], new_memory: Optional[str],
                   event: str, *, created_at: Optional[str] = None, updated_at: Optional[str] = None,
                   is_deleted: int = 0, actor_id: Optional[str] = None, role: Optional[str] = None) -> None:
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute("""
                    INSERT INTO history (
                        id, memory_id, old_memory, new_memory, event,
                        created_at, updated_at, is_deleted, actor_id, role
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (str(uuid.uuid4()), memory_id, old_memory, new_memory, event,
                     created_at, updated_at, is_deleted, actor_id, role))
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to add history record: {e}")
                raise

    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self.connection.execute("""
                SELECT id, memory_id, old_memory, new_memory, event,
                       created_at, updated_at, is_deleted, actor_id, role
                FROM history WHERE memory_id = ?
                ORDER BY created_at ASC, DATETIME(updated_at) ASC
            """, (memory_id,))
            rows = cur.fetchall()

        return [
            {
                "id": r[0], "memory_id": r[1], "old_memory": r[2], "new_memory": r[3],
                "event": r[4], "created_at": r[5], "updated_at": r[6], "is_deleted": bool(r[7]),
                "actor_id": r[8], "role": r[9],
            }
            for r in rows
        ]

    def reset(self) -> None:
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                self.connection.execute("DROP TABLE IF EXISTS history")
                self.connection.execute("COMMIT")
                self._create_history_table()
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to reset history table: {e}")
                raise

    def close(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None


class PostgreSQLHistoryManager(BaseHistoryManager):
    """PostgreSQL历史数据库管理器"""

    def __init__(self, host: str = "localhost", port: int = 5432, database: str = "mem0_history",
                 user: str = "postgres", password: str = "", table_name: str = "history"):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError:
            raise ImportError("psycopg2 is required for PostgreSQL support. Install with: pip install psycopg2-binary")

        self.table_name = table_name
        self._lock = threading.Lock()

        # 连接数据库
        self.connection = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        self.connection.autocommit = False

        logger.info(f"Connected to PostgreSQL: {host}:{port}/{database}")
        self._create_history_table()

    def _create_history_table(self) -> None:
        with self._lock:
            try:
                with self.connection.cursor() as cur:
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {self.table_name} (
                            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            memory_id    TEXT,
                            old_memory   TEXT,
                            new_memory   TEXT,
                            event        TEXT,
                            created_at   TIMESTAMP,
                            updated_at   TIMESTAMP,
                            is_deleted   BOOLEAN DEFAULT FALSE,
                            actor_id     TEXT,
                            role         TEXT
                        )
                    """)

                    # 创建索引以提高查询性能
                    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_memory_id ON {self.table_name}(memory_id)")
                    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_created_at ON {self.table_name}(created_at)")

                self.connection.commit()
                logger.info(f"PostgreSQL history table '{self.table_name}' created successfully")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"Failed to create PostgreSQL history table: {e}")
                raise

    def add_history(self, memory_id: str, old_memory: Optional[str], new_memory: Optional[str],
                   event: str, *, created_at: Optional[str] = None, updated_at: Optional[str] = None,
                   is_deleted: int = 0, actor_id: Optional[str] = None, role: Optional[str] = None) -> None:
        with self._lock:
            try:
                with self.connection.cursor() as cur:
                    cur.execute(f"""
                        INSERT INTO {self.table_name} (
                            memory_id, old_memory, new_memory, event,
                            created_at, updated_at, is_deleted, actor_id, role
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (memory_id, old_memory, new_memory, event,
                         created_at, updated_at, bool(is_deleted), actor_id, role))
                self.connection.commit()
            except Exception as e:
                self.connection.rollback()
                logger.error(f"Failed to add PostgreSQL history record: {e}")
                raise

    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            with self.connection.cursor() as cur:
                cur.execute(f"""
                    SELECT id, memory_id, old_memory, new_memory, event,
                           created_at, updated_at, is_deleted, actor_id, role
                    FROM {self.table_name} WHERE memory_id = %s
                    ORDER BY created_at ASC, updated_at ASC
                """, (memory_id,))
                rows = cur.fetchall()

        return [
            {
                "id": str(r[0]), "memory_id": r[1], "old_memory": r[2], "new_memory": r[3],
                "event": r[4], "created_at": r[5], "updated_at": r[6], "is_deleted": r[7],
                "actor_id": r[8], "role": r[9],
            }
            for r in rows
        ]

    def reset(self) -> None:
        with self._lock:
            try:
                with self.connection.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {self.table_name}")
                self.connection.commit()
                self._create_history_table()
                logger.info(f"PostgreSQL history table '{self.table_name}' reset successfully")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"Failed to reset PostgreSQL history table: {e}")
                raise

    def close(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None


class MySQLHistoryManager(BaseHistoryManager):
    """MySQL历史数据库管理器"""

    def __init__(self, host: str = "localhost", port: int = 3306, database: str = "mem0_history",
                 user: str = "root", password: str = "", table_name: str = "history"):
        try:
            import mysql.connector
        except ImportError:
            raise ImportError("mysql-connector-python is required for MySQL support. Install with: pip install mysql-connector-python")

        self.table_name = table_name
        self._lock = threading.Lock()

        # 连接数据库
        self.connection = mysql.connector.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            autocommit=False
        )

        logger.info(f"Connected to MySQL: {host}:{port}/{database}")
        self._create_history_table()

    def _create_history_table(self) -> None:
        with self._lock:
            try:
                with self.connection.cursor() as cur:
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {self.table_name} (
                            id           CHAR(36) PRIMARY KEY DEFAULT (UUID()),
                            memory_id    TEXT,
                            old_memory   TEXT,
                            new_memory   TEXT,
                            event        TEXT,
                            created_at   DATETIME,
                            updated_at   DATETIME,
                            is_deleted   BOOLEAN DEFAULT FALSE,
                            actor_id     TEXT,
                            role         TEXT
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """)

                    # 创建索引
                    cur.execute(f"CREATE INDEX idx_{self.table_name}_memory_id ON {self.table_name}(memory_id(50))")
                    cur.execute(f"CREATE INDEX idx_{self.table_name}_created_at ON {self.table_name}(created_at)")

                self.connection.commit()
                logger.info(f"MySQL history table '{self.table_name}' created successfully")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"Failed to create MySQL history table: {e}")
                raise

    def add_history(self, memory_id: str, old_memory: Optional[str], new_memory: Optional[str],
                   event: str, *, created_at: Optional[str] = None, updated_at: Optional[str] = None,
                   is_deleted: int = 0, actor_id: Optional[str] = None, role: Optional[str] = None) -> None:
        with self._lock:
            try:
                with self.connection.cursor() as cur:
                    cur.execute(f"""
                        INSERT INTO {self.table_name} (
                            memory_id, old_memory, new_memory, event,
                            created_at, updated_at, is_deleted, actor_id, role
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (memory_id, old_memory, new_memory, event,
                         created_at, updated_at, bool(is_deleted), actor_id, role))
                self.connection.commit()
            except Exception as e:
                self.connection.rollback()
                logger.error(f"Failed to add MySQL history record: {e}")
                raise

    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            with self.connection.cursor() as cur:
                cur.execute(f"""
                    SELECT id, memory_id, old_memory, new_memory, event,
                           created_at, updated_at, is_deleted, actor_id, role
                    FROM {self.table_name} WHERE memory_id = %s
                    ORDER BY created_at ASC, updated_at ASC
                """, (memory_id,))
                rows = cur.fetchall()

        return [
            {
                "id": r[0], "memory_id": r[1], "old_memory": r[2], "new_memory": r[3],
                "event": r[4], "created_at": r[5], "updated_at": r[6], "is_deleted": bool(r[7]),
                "actor_id": r[8], "role": r[9],
            }
            for r in rows
        ]

    def reset(self) -> None:
        with self._lock:
            try:
                with self.connection.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {self.table_name}")
                self.connection.commit()
                self._create_history_table()
                logger.info(f"MySQL history table '{self.table_name}' reset successfully")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"Failed to reset MySQL history table: {e}")
                raise

    def close(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None


def create_history_manager(db_type: str = "sqlite", **kwargs) -> BaseHistoryManager:
    """
    工厂函数：根据数据库类型创建相应的历史管理器

    Args:
        db_type: 数据库类型 ("sqlite", "postgresql", "mysql")
        **kwargs: 数据库连接参数

    Returns:
        相应的历史管理器实例
    """

    if db_type.lower() == "sqlite":
        db_path = kwargs.get("db_path", ":memory:")
        return SQLiteHistoryManager(db_path)

    elif db_type.lower() == "postgresql":
        return PostgreSQLHistoryManager(
            host=kwargs.get("host", "localhost"),
            port=kwargs.get("port", 5432),
            database=kwargs.get("database", "mem0_history"),
            user=kwargs.get("user", "postgres"),
            password=kwargs.get("password", ""),
            table_name=kwargs.get("table_name", "history")
        )

    elif db_type.lower() == "mysql":
        return MySQLHistoryManager(
            host=kwargs.get("host", "localhost"),
            port=kwargs.get("port", 3306),
            database=kwargs.get("database", "mem0_history"),
            user=kwargs.get("user", "root"),
            password=kwargs.get("password", ""),
            table_name=kwargs.get("table_name", "history")
        )

    else:
        raise ValueError(f"Unsupported database type: {db_type}")


# 示例配置
HISTORY_DB_CONFIGS = {
    "sqlite": {
        "db_type": "sqlite",
        "db_path": "/app/history/history.db"
    },

    "postgresql": {
        "db_type": "postgresql",
        "host": os.getenv("HISTORY_DB_HOST", "localhost"),
        "port": int(os.getenv("HISTORY_DB_PORT", "5432")),
        "database": os.getenv("HISTORY_DB_NAME", "mem0_history"),
        "user": os.getenv("HISTORY_DB_USER", "postgres"),
        "password": os.getenv("HISTORY_DB_PASSWORD", ""),
        "table_name": "history"
    },

    "mysql": {
        "db_type": "mysql",
        "host": os.getenv("HISTORY_DB_HOST", "localhost"),
        "port": int(os.getenv("HISTORY_DB_PORT", "3306")),
        "database": os.getenv("HISTORY_DB_NAME", "mem0_history"),
        "user": os.getenv("HISTORY_DB_USER", "root"),
        "password": os.getenv("HISTORY_DB_PASSWORD", ""),
        "table_name": "history"
    }
}


if __name__ == "__main__":
    print("🗄️ Mem0历史数据库管理器")
    print("支持的数据库类型:")
    print("  - SQLite (默认)")
    print("  - PostgreSQL")
    print("  - MySQL")
    print()
    print("使用示例:")
    print("  manager = create_history_manager('postgresql', host='localhost', database='mem0')")
    print("  manager.add_history(memory_id='123', event='create', new_memory='test')")
    print("  history = manager.get_history('123')")