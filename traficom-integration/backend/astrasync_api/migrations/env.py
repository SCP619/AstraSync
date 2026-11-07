"""Alembic environment. Runs only on the connection given by ``db.run_migrations``."""

from alembic import context

from astrasync_api import case_tables, library_tables  # noqa: F401 - registers the tables.
from astrasync_api.db import Base

connection = context.config.attributes["connection"]
context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
with context.begin_transaction():
    context.run_migrations()
