import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings


def build_database_url():
    pg_host = os.getenv("PGHOST")
    pg_port = os.getenv("PGPORT")
    pg_user = os.getenv("PGUSER")
    pg_password = os.getenv("PGPASSWORD")
    pg_database = os.getenv("PGDATABASE")

    if all([pg_host, pg_port, pg_user, pg_password, pg_database]):
        return URL.create(
            drivername="postgresql+psycopg",
            username=pg_user,
            password=pg_password,
            host=pg_host,
            port=int(pg_port),
            database=pg_database,
        )

    database_url = os.getenv("DATABASE_URL") or settings.database_url

    if database_url and "${{" not in str(database_url):
        database_url = str(database_url)

        if database_url.startswith("postgres://"):
            return database_url.replace(
                "postgres://", "postgresql+psycopg://", 1
            )

        if database_url.startswith("postgresql://"):
            return database_url.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )

        return database_url

    return "sqlite:///./propagent.db"


database_url = build_database_url()

connect_args = {}
if str(database_url).startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
