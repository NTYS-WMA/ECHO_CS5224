#!/usr/bin/env python3
"""
MongoDB Initialization Script for UserProfile

This script creates the necessary MongoDB collection and indexes
for the UserProfile additional_profile storage.

Usage:
    python scripts/init_mongodb.py

Environment variables required:
    - MONGODB_URI: MongoDB connection URI
    - MONGODB_DATABASE: MongoDB database name
"""

import os
import sys
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Default values
DEFAULT_COLLECTION = "user_additional_profile"


def init_mongodb():
    """Initialize MongoDB collection and indexes"""

    # Get configuration from environment
    mongo_uri = os.getenv("MONGODB_URI")
    database_name = os.getenv("MONGODB_DATABASE")

    if not mongo_uri:
        print("ERROR: MONGODB_URI environment variable is not set")
        sys.exit(1)

    if not database_name:
        print("ERROR: MONGODB_DATABASE environment variable is not set")
        sys.exit(1)

    print(f"Connecting to MongoDB: {database_name}")

    try:
        # Connect to MongoDB
        client = MongoClient(mongo_uri)
        db = client[database_name]

        # Test connection
        client.admin.command('ping')
        print("✓ MongoDB connection successful")

        # Create collection
        collection_name = DEFAULT_COLLECTION
        if collection_name not in db.list_collection_names():
            db.create_collection(collection_name)
            print(f"✓ Collection '{collection_name}' created")
        else:
            print(f"✓ Collection '{collection_name}' already exists")

        collection = db[collection_name]

        # Create indexes
        print("Creating indexes...")

        # Unique index on user_id
        collection.create_index("user_id", unique=True)
        print("✓ Index created: user_id (unique)")

        # Indexes on sub-document ids for faster queries
        collection.create_index("interests.id")
        print("✓ Index created: interests.id")

        collection.create_index("skills.id")
        print("✓ Index created: skills.id")

        collection.create_index("personality.id")
        print("✓ Index created: personality.id")

        collection.create_index("social_context.name")
        print("✓ Index created: social_context.name")

        collection.create_index("learning_preferences.name")
        print("✓ Index created: learning_preferences.name")

        # List all indexes
        print("\nAll indexes:")
        for index in collection.list_indexes():
            print(f"  - {index['name']}: {index['key']}")

        print("\n✅ MongoDB initialization completed successfully!")
        print(f"Database: {database_name}")
        print(f"Collection: {collection_name}")

        # Close connection
        client.close()

    except PyMongoError as e:
        print(f"\n❌ MongoDB error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    init_mongodb()
