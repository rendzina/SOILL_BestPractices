"""
Create_SOILL_Best_Practices_database.py
Prof. S. Hallett, Cranfield University
19/05/2026
======================================

Creates and prepares the MongoDB database for the SOILL Catalogue of Best
Practices (T4.4). Configuration is read from .env (MONGO_URI, MONGO_DB,
MONGO_COLLECTION).

The webscrape collection stores articles collected by SOILL_scrape.py.

Usage:
    python Create_SOILL_Best_Practices_database.py
    python Create_SOILL_Best_Practices_database.py --reset   # drop collection first

Prerequisites:
    MongoDB running locally or accessible on the cloud (see .env MONGO_URI)
    pip install pymongo python-dotenv
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import CollectionInvalid, OperationFailure

from config import MONGO_COLLECTION, MONGO_DB, MONGO_URI


def get_article_schema() -> Dict[str, Any]:
    """JSON schema validator for scraped article documents."""
    return {
        '$jsonSchema': {
            'bsonType': 'object',
            'required': [
                'title',
                'description',
                'url',
                'scrape_date',
                'content_type',
                'source',
                'seed_url',
                'project_name',
                'source_domain',
            ],
            'properties': {
                '_id': {
                    'bsonType': 'objectId',
                    'description': 'Unique document identifier',
                },
                'title': {
                    'bsonType': 'string',
                    'description': 'Article heading extracted from HTML',
                },
                'description': {
                    'bsonType': 'string',
                    'description': 'Article body text extracted from HTML',
                },
                'url': {
                    'bsonType': 'string',
                    'description': 'Canonical or linked URL for the article',
                },
                'scrape_date': {
                    'bsonType': 'date',
                    'description': 'UTC timestamp when the article was scraped',
                },
                'content_type': {
                    'enum': ['article'],
                    'description': 'Document type (scraped HTML article)',
                },
                'heading_level': {
                    'bsonType': ['string', 'null'],
                    'description': 'HTML heading tag used for the title (e.g. h1, h2)',
                },
                'source': {
                    'bsonType': 'string',
                    'description': 'Page URL where the article block was found',
                },
                'seed_url': {
                    'bsonType': 'string',
                    'description': 'Seed URL from urls_to_scrape.txt for this website',
                },
                'project_name': {
                    'bsonType': 'string',
                    'description': 'Project label from urls_to_scrape.txt',
                },
                'source_domain': {
                    'bsonType': 'string',
                    'description': 'Hostname of the crawled website',
                },
            },
            'additionalProperties': True,
        },
    }


def get_sample_article() -> Dict[str, Any]:
    """Sample document matching the schema (removed after verification)."""
    now = datetime.now(timezone.utc)
    return {
        'title': 'SOILL database setup — sample article',
        'description': (
            'This is a placeholder article inserted when initialising the '
            'SOILL_catalogue database. It can be deleted after verification.'
        ),
        'url': 'https://example.soill.local/setup-sample',
        'scrape_date': now,
        'content_type': 'article',
        'heading_level': 'h1',
        'source': 'https://example.soill.local/setup-sample',
        'seed_url': 'https://example.soill.local/',
        'project_name': '_SETUP_SAMPLE_',
        'source_domain': 'example.soill.local',
    }


def create_indexes(collection: Any) -> None:
    """Create indexes to support catalogue queries and screening."""
    collection.create_index([('project_name', ASCENDING)], name='idx_project_name')
    collection.create_index([('source_domain', ASCENDING)], name='idx_source_domain')
    collection.create_index([('scrape_date', DESCENDING)], name='idx_scrape_date')
    collection.create_index(
        [('project_name', ASCENDING), ('url', ASCENDING), ('title', ASCENDING)],
        name='idx_project_url_title',
    )
    print('Indexes created (or already present).')


def create_database_and_collection(reset: bool = False) -> None:
    """Create the database collection, validator, and indexes."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

    try:
        client.server_info()
        print(f'Connected to MongoDB: {MONGO_URI}')
    except Exception as exc:
        print(f'ERROR: Cannot connect to MongoDB: {exc}')
        print('Ensure Docker MongoDB is running and MONGO_URI in .env is correct.')
        sys.exit(1)

    db = client[MONGO_DB]
    schema = get_article_schema()

    print(f'Database : {MONGO_DB}')
    print(f'Collection: {MONGO_COLLECTION}')

    existing = MONGO_COLLECTION in db.list_collection_names()

    if reset and existing:
        db.drop_collection(MONGO_COLLECTION)
        print(f'Dropped existing collection: {MONGO_COLLECTION}')
        existing = False

    if not existing:
        try:
            db.create_collection(
                MONGO_COLLECTION,
                validator=schema,
                validationLevel='moderate',
                validationAction='error',
            )
            print(f'Created collection: {MONGO_COLLECTION}')
        except CollectionInvalid as exc:
            print(f'ERROR: Could not create collection: {exc}')
            sys.exit(1)
    else:
        try:
            db.command({
                'collMod': MONGO_COLLECTION,
                'validator': schema,
                'validationLevel': 'moderate',
                'validationAction': 'error',
            })
            print(f'Updated validator on existing collection: {MONGO_COLLECTION}')
        except OperationFailure as exc:
            print(f'ERROR: Could not update collection validator: {exc}')
            sys.exit(1)

    collection = db[MONGO_COLLECTION]
    create_indexes(collection)

    # Insert and verify sample document
    sample = get_sample_article()
    result = collection.insert_one(sample)
    print(f'\nSample article inserted with _id: {result.inserted_id}')

    retrieved = collection.find_one({'_id': result.inserted_id})
    print('\nSample document retrieved:')
    print(json.dumps(retrieved, default=str, indent=2))

    collection.delete_one({'_id': result.inserted_id})
    print('\nSample document removed (collection is ready for SOILL_scrape.py).')

    doc_count = collection.count_documents({})
    print(f'\nCollection ready: {doc_count} document(s) in {MONGO_DB}.{MONGO_COLLECTION}')
    print('Run: python SOILL_scrape.py')

    client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Create and prepare the SOILL MongoDB article collection.',
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Drop the collection before recreating (deletes all existing articles).',
    )
    args = parser.parse_args()

    if args.reset:
        confirm = input(
            f'This will delete all documents in {MONGO_DB}.{MONGO_COLLECTION}. '
            'Continue? [y/N]: '
        )
        if confirm.strip().lower() != 'y':
            print('Aborted.')
            sys.exit(0)

    create_database_and_collection(reset=args.reset)


if __name__ == '__main__':
    main()
