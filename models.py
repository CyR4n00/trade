import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

class StrategyParam(Base):
    __tablename__ = 'strategy_params'
    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False, unique=True)
    short_window = Column(Integer, nullable=False)
    long_window = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Trade(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False)
    action = Column(String(10), nullable=False) # 'BUY' or 'SELL'
    price = Column(Float, nullable=False)
    shares = Column(Integer, nullable=False)
    pnl = Column(Float, nullable=True) # Profit/Loss realized on SELL
    timestamp = Column(DateTime, default=datetime.utcnow)

class Account(Base):
    __tablename__ = 'account'
    id = Column(Integer, primary_key=True)
    balance = Column(Float, nullable=False, default=1000000.0) # 余力
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

engine = create_engine('sqlite:///trading.db')
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
