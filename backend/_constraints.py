import asyncio
import asyncpg

DSN = "postgresql://postgres:postgrespassword123@localhost:5432/postgres"

async def main():
    conn = await asyncpg.connect(DSN)
    exists = await conn.fetchval("select 1 from pg_database where datname='siet_fresh_test'")
    if exists:
        await conn.execute("drop database siet_fresh_test")
    await conn.execute("create database siet_fresh_test")
    print("created siet_fresh_test")
    await conn.close()

    conn2 = await asyncpg.connect("postgresql://postgres:postgrespassword123@localhost:5432/siet_fresh_test")
    print("verify:", await conn2.fetchval("select current_database()"))
    await conn2.close()

asyncio.run(main())