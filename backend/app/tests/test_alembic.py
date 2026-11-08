import os
import tempfile
import pytest
from alembic import command
from alembic.config import Config


def test_alembic_upgrade_head_sqlite():
    """Verify that alembic upgrade head and alembic check run cleanly on an empty DB."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_alembic.db").replace("\\", "/")
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ini_path = os.path.join(backend_dir, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    try:
        command.upgrade(cfg, "head")
        command.check(cfg)
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass


def test_alembic_postgres_migration():
    """Verify that alembic upgrade head runs cleanly against a real Postgres instance if configured."""
    db_url = os.environ.get("TEST_POSTGRES_URL")
    if not db_url:
        pytest.skip("No TEST_POSTGRES_URL configured; skipping live Postgres migration test")

    import sqlalchemy as sa
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ini_path = os.path.join(backend_dir, "alembic.ini")

    engine = sa.create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(sa.text("DROP SCHEMA IF EXISTS alembic_fresh_test CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA alembic_fresh_test"))
        conn.execute(sa.text("SET search_path TO alembic_fresh_test"))
        conn.commit()

        cfg = Config(ini_path)
        cfg.attributes["connection"] = conn

        try:
            command.upgrade(cfg, "head")
            command.check(cfg)
        finally:
            conn.execute(sa.text("DROP SCHEMA IF EXISTS alembic_fresh_test CASCADE"))
            conn.commit()
