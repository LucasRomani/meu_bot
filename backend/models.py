from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    credentials = relationship('SavedCredential', back_populates='user', cascade='all, delete-orphan')
    executions = relationship('Execution', back_populates='user', cascade='all, delete-orphan')


class SavedCredential(Base):
    __tablename__ = 'saved_credentials'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    system = Column(String(50), nullable=False)  # 'sischef' or 'qrpedir'
    label = Column(String(100), default='')       # friendly name, e.g. "Loja Centro"
    username_enc = Column(Text, nullable=False)    # Fernet encrypted
    password_enc = Column(Text, nullable=False)    # Fernet encrypted
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship('User', back_populates='credentials')


class Execution(Base):
    __tablename__ = 'executions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    task_name = Column(String(100), nullable=False)
    status = Column(String(30), default='running')  # running, completed, failed, stopped
    csv_filename = Column(String(255), default='')
    items_total = Column(Integer, default=0)
    items_done = Column(Integer, default=0)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)

    user = relationship('User', back_populates='executions')
    logs = relationship('LogEntry', back_populates='execution', cascade='all, delete-orphan',
                        order_by='LogEntry.timestamp')


class LogEntry(Base):
    __tablename__ = 'log_entries'

    id = Column(Integer, primary_key=True)
    execution_id = Column(Integer, ForeignKey('executions.id', ondelete='CASCADE'), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    message = Column(Text, nullable=False)

    execution = relationship('Execution', back_populates='logs')
