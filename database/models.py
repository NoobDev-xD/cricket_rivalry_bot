from sqlalchemy import Column, Integer, String, Boolean, BigInteger, DateTime, Float
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    full_name = Column(String, default="Player")
    total_runs = Column(Integer, default=0)
    total_balls = Column(Integer, default=0)
    total_wickets = Column(Integer, default=0)
    matches_played = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, index=True)
    mode = Column(String, default="team")
    host_id = Column(BigInteger)
    status = Column(String, default="lobby")

    overs = Column(Integer, default=5)
    max_wickets = Column(Integer, default=5)
    powerplay = Column(Boolean, default=False)

    team_a = Column(String, default="")
    team_b = Column(String, default="")
    team_a_captain = Column(BigInteger, nullable=True)
    team_b_captain = Column(BigInteger, nullable=True)

    batting_team = Column(String, default="A")
    current_innings = Column(Integer, default=1)

    team_a_runs = Column(Integer, default=0)
    team_a_wickets = Column(Integer, default=0)
    team_a_balls = Column(Integer, default=0)

    team_b_runs = Column(Integer, default=0)
    team_b_wickets = Column(Integer, default=0)
    team_b_balls = Column(Integer, default=0)

    target = Column(Integer, nullable=True)

    striker_id = Column(BigInteger, nullable=True)
    non_striker_id = Column(BigInteger, nullable=True)
    bowler_id = Column(BigInteger, nullable=True)

    free_hit = Column(Boolean, default=False)
    waiting_for = Column(String, nullable=True)
    pending_bowler_num = Column(Integer, nullable=True)

    potm_runs = Column(Integer, default=0)
    potm_wickets = Column(Integer, default=0)
    potm_id = Column(BigInteger, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
