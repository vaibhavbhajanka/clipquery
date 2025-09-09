from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus
from app.core.logging_config import get_logger

logger = get_logger("database")

load_dotenv()

# Fetch Supabase connection variables
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")

# Construct the SQLAlchemy connection string (URL-encode password to handle special characters)
DATABASE_URL = f"postgresql+psycopg2://{USER}:{quote_plus(PASSWORD)}@{HOST}:{PORT}/{DBNAME}?sslmode=require"

# Create SQLAlchemy engine with connection pooling for Supabase
# pool_pre_ping=True tests connections before using them to handle stale connections
# pool_recycle=300 recycles connections every 5 minutes (before Supabase timeout)
# pool_size and max_overflow control the connection pool size
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Test connections before using them
    pool_size=10,        # Number of connections to maintain in pool
    max_overflow=20,     # Maximum overflow connections
    pool_recycle=300,    # Recycle connections every 5 minutes
    connect_args={
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }
)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create all tables
def create_tables():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.error(f"Failed to create database tables", exc_info=True)
        raise