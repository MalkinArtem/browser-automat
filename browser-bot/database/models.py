from sqlalchemy import Column, Integer, String, Boolean

from database.db import Base


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    profile_id = Column(String(255), nullable=True)
    activate = Column(Boolean, nullable=True)
