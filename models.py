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
    min_volume = Column(Integer, nullable=False, default=1000000)
    price_change_pct = Column(Float, nullable=False, default=0.01)
    take_profit_pct = Column(Float, nullable=False, default=0.10)
    stop_loss_pct = Column(Float, nullable=False, default=0.05)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Trade(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False)
    action = Column(String(10), nullable=False) # 'BUY' or 'SELL'
    trade_type = Column(String(20), nullable=False, default='CASH') # 'CASH' (現物), 'MARGIN_LONG' (信用買い), 'MARGIN_SHORT' (信用売り)
    price = Column(Float, nullable=False)
    shares = Column(Integer, nullable=False)
    pnl = Column(Float, nullable=True) # Profit/Loss realized on SELL
    timestamp = Column(DateTime, default=datetime.utcnow)

class Account(Base):
    __tablename__ = 'account'
    id = Column(Integer, primary_key=True)
    balance = Column(Float, nullable=False, default=1000000.0) # 現物買付余力
    margin_deposit = Column(Float, nullable=False, default=1000000.0) # 委託保証金 (Margin Deposit)
    margin_power = Column(Float, nullable=False, default=3000000.0) # 信用建余力 (通常保証金の約3倍)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AnalysisReport(Base):
    __tablename__ = 'analysis_reports'
    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False)
    trade_id = Column(Integer, nullable=True) # Linked to a specific sell trade
    good_points = Column(String(500), nullable=True) # 良かった点
    bad_points = Column(String(500), nullable=True) # 悪かった点・改善点
    summary = Column(String(500), nullable=True) # 分析サマリー
    timestamp = Column(DateTime, default=datetime.utcnow)

engine = create_engine('sqlite:///trading.db')
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
