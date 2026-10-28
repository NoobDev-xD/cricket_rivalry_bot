from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, desc
from database.models import Base, User, Match
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./cricket.db")
engine = create_async_engine(DATABASE_URL, echo=False)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_or_create_user(session, user_id, username=None, full_name=None):
    r = await session.execute(select(User).where(User.id == user_id))
    user = r.scalar_one_or_none()
    if not user:
        user = User(id=user_id, username=username, full_name=full_name or "Player")
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        if full_name and user.full_name != full_name:
            user.full_name = full_name
            await session.commit()
    return user

async def get_match(session, chat_id):
    r = await session.execute(
        select(Match).where(Match.chat_id == chat_id, Match.status != "finished")
    )
    return r.scalar_one_or_none()

async def get_leaderboard(session, limit=10):
    r = await session.execute(
        select(User).order_by(desc(User.total_runs)).limit(limit)
    )
    return r.scalars().all()

async def name_of(session, user_id):
    r = await session.execute(select(User).where(User.id == user_id))
    u = r.scalar_one_or_none()
    return u.full_name if u else f"User{user_id}"
