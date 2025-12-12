# backend/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Wir nutzen eine einfache SQLite Datenbank (eine Datei)
SQLALCHEMY_DATABASE_URL = "sqlite:///./plants.db"

# connect_args={"check_same_thread": False} ist nur für SQLite notwendig
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()