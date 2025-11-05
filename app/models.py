from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class ReportStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    avatar_url = Column(String(255), nullable=True)
    gender = Column(String(10), nullable=True)  # male|female|other|unset
    bio = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    theme = Column(String(10), nullable=True)  # light|dark|system
    favorites = Column(Text, nullable=True)  # JSON string
    public_profile = Column(Boolean, default=False, nullable=False)
    last_active_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    reports = relationship(
        "SpeciesReport",
        back_populates="reporter",
        foreign_keys=lambda: [SpeciesReport.reporter_id],
    )


class SpeciesReport(Base):
    __tablename__ = "species_reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # taxonomy fields (optional)
    phylum = Column(String(100), nullable=True, index=True)
    class_name = Column(String(100), nullable=True, index=True)
    order_name = Column(String(100), nullable=True, index=True)
    family = Column(String(100), nullable=True, index=True)
    genus = Column(String(100), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    species_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    location_text = Column(String(255), nullable=True)
    photo_paths = Column(Text, nullable=True)  # JSON stored as simple comma-separated for simplicity
    status = Column(String(20), default=ReportStatus.pending.value, index=True)
    review_note = Column(Text, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    reporter = relationship("User", back_populates="reports", foreign_keys=[reporter_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])


class PointsLedger(Base):
    __tablename__ = "points_ledger"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    delta = Column(Integer, nullable=False)  # positive for earn, negative for spend
    reason = Column(String(50), nullable=False)  # donate|report|signin|quest|redeem|draw|adjust
    ref_type = Column(String(50), nullable=True)
    ref_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Donation(Base):
    __tablename__ = "donations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    report_id = Column(Integer, ForeignKey("species_reports.id"), index=True, nullable=True)
    species_name = Column(String(200), nullable=True)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(10), default="CNY", nullable=False)
    provider = Column(String(20), default="alipay", nullable=False)
    status = Column(String(20), default="paid", nullable=False)  # mock paid
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DailySignin(Base):
    __tablename__ = "daily_signins"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    date = Column(String(10), index=True, nullable=False)  # YYYY-MM-DD UTC
    points = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class QuestLog(Base):
    __tablename__ = "quest_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    code = Column(String(50), index=True, nullable=False)  # view_5 | share_1 | report_1
    date = Column(String(10), index=True, nullable=False)  # YYYY-MM-DD UTC
    progress = Column(Integer, default=0, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    rewarded = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ShopItem(Base):
    __tablename__ = "shop_items"

    id = Column(Integer, primary_key=True)
    kind = Column(String(20), nullable=False)  # virtual | physical
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    points_cost = Column(Integer, nullable=False)
    stock = Column(Integer, nullable=True)  # null = unlimited
    media_url = Column(String(255), nullable=True)
    status = Column(String(20), default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Redemption(Base):
    __tablename__ = "redemptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    item_id = Column(Integer, ForeignKey("shop_items.id"), index=True, nullable=False)
    points_cost = Column(Integer, nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    shipping_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
