"""
PostgreSQL Manager for UserProfile basic_info storage
"""

import logging
from contextlib import contextmanager
from typing import Dict, Any, Optional
from datetime import datetime

# Try to import psycopg (psycopg3) first, then fall back to psycopg2
try:
    from psycopg_pool import ConnectionPool
    PSYCOPG_VERSION = 3
    logger = logging.getLogger(__name__)
    logger.info("PostgresManager: Using psycopg (psycopg3)")
except ImportError:
    try:
        from psycopg2.pool import ThreadedConnectionPool as ConnectionPool
        PSYCOPG_VERSION = 2
        logger = logging.getLogger(__name__)
        logger.info("PostgresManager: Using psycopg2")
    except ImportError:
        raise ImportError(
            "Neither 'psycopg' nor 'psycopg2' library is available. "
            "Please install one of them using 'pip install psycopg[pool]' or 'pip install psycopg2'"
        )

logger = logging.getLogger(__name__)


class PostgresManager:
    """
    PostgreSQL manager for UserProfile basic_info storage

    Manages connection pool and CRUD operations for user_profile table
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PostgreSQL connection pool

        Args:
            config: Configuration dict with connection parameters
                - host: Database host
                - port: Database port
                - user: Database user
                - password: Database password
                - database: Database name
                - minconn: Minimum connections in pool (default 1)
                - maxconn: Maximum connections in pool (default 5)
        """
        self.config = config
        self.connection_pool = None
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize connection pool"""
        try:
            connection_string = (
                f"postgresql://{self.config['user']}:{self.config['password']}"
                f"@{self.config['host']}:{self.config['port']}/{self.config['database']}"
            )

            minconn = self.config.get('minconn', 1)
            maxconn = self.config.get('maxconn', 5)

            if PSYCOPG_VERSION == 3:
                self.connection_pool = ConnectionPool(
                    connection_string,
                    min_size=minconn,
                    max_size=maxconn,
                    timeout=30.0,
                    open=True  # Explicitly open the pool
                )
            else:
                self.connection_pool = ConnectionPool(
                    minconn=minconn,
                    maxconn=maxconn,
                    dsn=connection_string
                )

            logger.info("PostgreSQL connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
            raise

    @contextmanager
    def _get_connection(self):
        """Get a connection from the pool"""
        conn = None
        try:
            if PSYCOPG_VERSION == 3:
                with self.connection_pool.connection() as conn:
                    yield conn
            else:
                conn = self.connection_pool.getconn()
                yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if PSYCOPG_VERSION == 2 and conn:
                self.connection_pool.putconn(conn)

    def create_table(self):
        """Create user_profile table if not exists"""
        create_table_query = """
        CREATE SCHEMA IF NOT EXISTS user_profile;

        CREATE TABLE IF NOT EXISTS user_profile.user_profile (
            user_id VARCHAR(50) PRIMARY KEY,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            name VARCHAR(100),
            nickname VARCHAR(100),
            english_name VARCHAR(100),
            birthday DATE,
            gender VARCHAR(10),
            nationality VARCHAR(50),
            hometown VARCHAR(100),
            current_city VARCHAR(100),
            timezone VARCHAR(50),
            language VARCHAR(50),
            school_name VARCHAR(200),
            grade VARCHAR(50),
            class_name VARCHAR(50)
        );

        CREATE INDEX IF NOT EXISTS idx_user_profile_name ON user_profile.user_profile(name);
        CREATE INDEX IF NOT EXISTS idx_user_profile_updated_at ON user_profile.user_profile(updated_at);
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(create_table_query)
                    conn.commit()
            logger.info("user_profile table created successfully")
        except Exception as e:
            logger.error(f"Failed to create user_profile table: {e}")
            raise

    def upsert(self, user_id: str, basic_info: Dict[str, Any]) -> bool:
        """
        Insert or update user basic_info

        Args:
            user_id: User ID
            basic_info: Basic information dict (name, birthday, etc.)

        Returns:
            True if successful
        """
        # Filter out None values
        filtered_info = {k: v for k, v in basic_info.items() if v is not None}

        if not filtered_info:
            logger.warning(f"No valid basic_info to upsert for user {user_id}")
            return False

        # Build dynamic UPSERT query
        fields = ['user_id', 'updated_at'] + list(filtered_info.keys())
        values = [user_id, datetime.now()] + list(filtered_info.values())

        placeholders = ', '.join(['%s'] * len(fields))
        field_names = ', '.join(fields)

        # Build UPDATE clause (exclude user_id and created_at)
        update_fields = [f"{field} = EXCLUDED.{field}" for field in fields if field not in ['user_id', 'created_at']]
        update_clause = ', '.join(update_fields)

        upsert_query = f"""
        INSERT INTO user_profile.user_profile ({field_names})
        VALUES ({placeholders})
        ON CONFLICT (user_id)
        DO UPDATE SET {update_clause}
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(upsert_query, values)
                    conn.commit()
            logger.info(f"Successfully upserted basic_info for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert basic_info for user {user_id}: {e}")
            raise

    def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user basic_info by user_id

        Args:
            user_id: User ID

        Returns:
            Dict with basic_info or None if not found
        """
        query = "SELECT * FROM user_profile.user_profile WHERE user_id = %s"

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (user_id,))
                    row = cursor.fetchone()

                    if not row:
                        return None

                    # Get column names
                    columns = [desc[0] for desc in cursor.description]

                    # Convert row to dict
                    result = dict(zip(columns, row))

                    # Convert date/datetime to ISO format
                    for key, value in result.items():
                        if isinstance(value, datetime):
                            result[key] = value.isoformat()
                        elif hasattr(value, 'isoformat'):  # date object
                            result[key] = value.isoformat()

                    return result
        except Exception as e:
            logger.error(f"Failed to get basic_info for user {user_id}: {e}")
            raise

    def delete(self, user_id: str) -> bool:
        """
        Delete user basic_info

        Args:
            user_id: User ID

        Returns:
            True if deleted successfully
        """
        query = "DELETE FROM user_profile.user_profile WHERE user_id = %s"

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (user_id,))
                    deleted_count = cursor.rowcount
                    conn.commit()

            if deleted_count > 0:
                logger.info(f"Successfully deleted basic_info for user {user_id}")
                return True
            else:
                logger.warning(f"No basic_info found to delete for user {user_id}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete basic_info for user {user_id}: {e}")
            raise

    def get_missing_fields(self, user_id: str) -> list:
        """
        Get list of missing basic_info fields for a user

        Args:
            user_id: User ID

        Returns:
            List of missing field names (fields that are NULL or empty)
        """
        # Define all expected basic_info fields (excluding system fields)
        ALL_FIELDS = [
            'name', 'nickname', 'english_name', 'birthday', 'gender',
            'nationality', 'hometown', 'current_city', 'timezone', 'language',
            'school_name', 'grade', 'class_name'
        ]

        try:
            # Get current basic_info
            basic_info = self.get(user_id)

            if not basic_info:
                # User doesn't exist, all fields are missing
                return ALL_FIELDS

            # Find missing fields (NULL or empty values)
            missing_fields = []
            for field in ALL_FIELDS:
                value = basic_info.get(field)
                if value is None or value == '':
                    missing_fields.append(field)

            return missing_fields
        except Exception as e:
            logger.error(f"Failed to get missing fields for user {user_id}: {e}")
            raise

    def close(self):
        """Close connection pool"""
        if self.connection_pool:
            self.connection_pool.close()
            logger.info("PostgreSQL connection pool closed")
