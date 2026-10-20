import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import delete, select, update

import fs_notifications_challenge.infrastructure.models as models
from fs_notifications_challenge.infrastructure.database import AsyncSessionLocal, engine
from fs_notifications_challenge.main import app

USERS = [
    {
        "email": "CoreyMSchafer@gmail.com",
        "password": "TestPassword1!",
        "profile": {
            "email": "co.Ms@example.com",
            "phone": "+1 201 555 0123"
        }
    },
    {
        "email": "TestEmail2@test.com",
        "password": "TestPassword2!",
        "profile": {
            "email": "contact_me@example.com",
            "phone": "+573124567890",
            "token": "J6a5YZ2KFOY2iOefjys2Tat:yF8XJF8Qw9"
        }
    },
    {
        "email": "TestEmail3@test.com",
        "password": "TestPassword3!",
        "profile": {
            "email": "contact_me@example.com",
            "phone": "+59899123456"
        }
    },
    {
        "email": "TestEmail4@test.com",
        "password": "TestPassword4!",
        "profile": {
            "email": "contact@example.com",
            "phone": "+51073123456"
        }
    },
    {
        "email": "TestEmail5@test.com",
        "password": "TestPassword5!",
        "profile": {
            "email": "other@example.com",
            "phone": "+573124567890",
            "token": "J6a5YZ2KFOY2iOefjys2Tat:yF8XJF8Qw9"
        }
    },
    {
        "email": "TestEmail6@test.com",
        "password": "TestPassword6!"
    },
]

NOTIFICATIONS = [
    {
        "title": "Why I Love FastAPI",
        "content": "FastAPI has completely changed how I build APIs. The automatic documentation, type hints, and async support make development so much faster. Plus, the performance is incredible!",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "Corey Schafer Has the Best YouTube Tutorials!",
        "content": "This was written by a viewer and definitely not by me... I mean him. Totally not written by him, but by me... a real viewer. Seriously, check out his channel for amazing Python content.",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "Async/Await Finally Clicked",
        "content": "I've been struggling with async programming for months, but FastAPI's approach finally made it click. Using 'async def' for endpoints and 'await' for database calls just makes sense.",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "Schafer? I Barely Know Her!",
        "content": "Is anyone actually reading these blog posts? Do they really need to say anything? I can keep going all day. At least AI can... Claude, keep going, please.",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "Pydantic Validation is Magic",
        "content": "The way Pydantic handles validation in FastAPI is incredible. Define your model with type hints, and boom - automatic validation, serialization, and documentation. No more writing validation code by hand!",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "From Flask to FastAPI",
        "content": "I made the switch from Flask to FastAPI last month. The learning curve was minimal, and the benefits are huge. Automatic OpenAPI docs, better performance, and native async support. No regrets!",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "Some of My Favorite Horror Movies",
        "content": "I love horror movies and practical effects. One of my favorites is 'The Thing'. Hereditary is a great modern one, but most people have seen it. One modern one I really liked that not as many people have seen is 'The Night House'. It's a slow burn but really effective. More psychological than jump-scare based.",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "Type Hints Changed My Life",
        "content": "I used to think type hints were just extra typing (pun intended). But after using FastAPI, I see how they enable incredible tooling - better autocomplete, automatic validation, and self-documenting code.",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "The Power of Dependency Injection",
        "content": "FastAPI's dependency injection system is so elegant. Need a database session? Just add it as a parameter. Need the current user? Same thing. It makes the code so clean and testable.",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "SQLAlchemy 2.0 Is Worth the Upgrade",
        "content": "If you're still using SQLAlchemy 1.x patterns, it's time to upgrade. The new 2.0 style with select() and mapped_column() is much more explicit and works beautifully with async.",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "Hot Take: Python > JavaScript for APIs",
        "content": "Yes, I said it. For backend APIs, Python with FastAPI beats Node.js. Fight me in the comments. (Just kidding, this blog doesn't have comments... yet.)",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "Understanding HTTP Status Codes",
        "content": "200 OK, 201 Created, 400 Bad Request, 404 Not Found, 500 Internal Server Error. Learn these codes - they're how your API communicates with the world. FastAPI makes it easy to return the right ones.",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "Some of My Favorite Video Games",
        "content": "The one I probably play the most, but not my favorite, is League of Legends... It's a love/hate relationship. My favorites are all single-player RPGs. The Elder Scrolls series (Especially Morrowind and Skyrim) were awesome. The Baldur's Gate series took up a lot of my time as a kid, and the 3rd one was great. I love that old isometric style of RPG, so I found Pillars of Eternity, which was fantastic, and Pathfinder: Kingmaker, which was a lot of fun too.",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "JWT Authentication Demystified",
        "content": "JSON Web Tokens seemed scary at first, but they're actually pretty simple. Encode some user data, sign it with a secret, and use it to verify requests. FastAPI + PyJWT makes it straightforward.",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "Tips for API Design",
        "content": "Use nouns for resources (/users, /posts), HTTP verbs for actions (GET, POST, PUT, DELETE), and return consistent responses. FastAPI's response_model helps enforce this consistency.",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "Path Parameters vs Query Parameters",
        "content": "Use path parameters for required resource identifiers (/users/123) and query parameters for optional filters (/posts?author=corey&limit=10). FastAPI handles both beautifully with automatic validation.",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "Error Handling Done Right",
        "content": "Don't just return 500 for everything! Use HTTPException to return meaningful status codes and messages. Your API consumers will thank you when debugging issues.",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "Why I Switched to UV",
        "content": "UV is blazingly fast for Python package management. Install packages in milliseconds instead of minutes. If you haven't tried it yet, you're missing out!",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "What About Favorite Books?",
        "content": "I don't read a lot of fiction. The last fiction book I read was 'The Martian' by Andy Weir, which I really enjoyed. But most of my reading is non-fiction. Some of my favorites are 'Meditations' by Marcus Aurelius, 'Conscious' by Annaka Harris, 'How to Die' by Seneca, and 'The Last Lecture' by Randy Pausch. The latest fiction book I'm reading through (and have been for a while) is 'House of Leaves' by Mark Z. Danielewski. It's... different, but awesome.",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "Testing FastAPI Applications",
        "content": "FastAPI's TestClient makes testing a breeze. Write tests for your endpoints, mock dependencies, and catch bugs before they hit production. Your future self will thank you.",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "Environment Variables and Security",
        "content": "Never hardcode secrets! Use environment variables and pydantic-settings to keep your API keys, database URLs, and JWT secrets safe. It's Security 101.",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "CORS: The Bane of Frontend Devs",
        "content": "Getting CORS errors? FastAPI's CORSMiddleware is your friend. Just remember: be specific about allowed origins in production. Don't use '*' unless you really mean it.",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "Async Database Queries",
        "content": "Blocking database calls in async code? That's a performance killer. Use async drivers like psycopg (for PostgreSQL) or aiosqlite to keep your event loop happy.",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "The Beauty of Response Models",
        "content": "Response models aren't just for documentation - they filter out sensitive fields automatically. Define what goes out, and Pydantic handles the rest.",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "Let's Talk Board Games",
        "content": "I love Settlers of Catan. It's a classic for a reason. I'm actually going to make a sword in my woodshop soon that will be my friend group's trophy for the annual Catan champion that we're going to call 'The Katana of Catan'. One thing I've always wanted to do, but never have, is play an in-person Dungeons & Dragons campaign. I've played so many D&D inspired video games, but never the real deal. Hopefully someday...",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "API Versioning Strategies",
        "content": "APIs evolve. Version them from day one! Whether you use URL prefixes (/v1/users) or headers, plan for change. Breaking changes without versioning breaks trust.",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "Background Tasks in FastAPI",
        "content": "Don't make users wait for emails to send or files to process. FastAPI's BackgroundTasks lets you return immediately while work continues in the background.",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "Rate Limiting Your API",
        "content": "Protect your API from abuse with rate limiting. Too many requests? Return 429 Too Many Requests. Your server (and your wallet) will thank you.",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "Documentation That Writes Itself",
        "content": "Add docstrings to your endpoints and they appear in Swagger UI. Add examples to your Pydantic models and they show up too. Documentation has never been this easy.",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "WebSockets with FastAPI",
        "content": "REST isn't the only game in town. FastAPI supports WebSockets for real-time communication. Chat apps, live updates, notifications - all possible!",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "Favorite Hobbies, You Ask?",
        "content": "Woodworking, hands down. I love making things with wood, but I wish I had more time for it. There's something special about making something with your own hands, with materials that are local. A lot of the stuff I've built came from trees that fell on my family's property. My stuff might not always be as good as something you buy in a store, but there's a story and a connection there that makes it better than anything I could buy elsewhere.",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "Custom Validators in Pydantic",
        "content": "Need validation beyond type checking? Pydantic's field_validator and model_validator decorators let you add custom logic. Validate emails, check password strength, whatever you need.",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "The ORM vs Raw SQL Debate",
        "content": "ORMs like SQLAlchemy add abstraction but can hide performance issues. Know when to use the ORM and when to drop to raw SQL. Both have their place.",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "Debugging Async Code",
        "content": "Async bugs can be tricky. Use logging liberally, understand the event loop, and don't mix sync and async without care. asyncio.run() is your entry point.",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "Containerizing FastAPI Apps",
        "content": "Docker + FastAPI = deployment bliss. Create a Dockerfile, build your image, and deploy anywhere. Consistency across environments is priceless.",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "Health Check Endpoints",
        "content": "Add a /health endpoint to your API. Load balancers and orchestrators need to know if your service is alive. Return 200 if healthy, details if not. I didn't do this in this tutorial, but there's only so much time in a video!",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "Hmm... What Else?",
        "content": "I'm running out of ideas for these blog posts. Maybe I should just write about how great FastAPI is... Oh wait, I've already done that multiple times. Well, if you're still reading, thanks for sticking with it! You're awesome.",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "Pagination: Don't Return Everything",
        "content": "Returning 10,000 records in one response? Please don't. Implement pagination with limit and offset (or better, cursor-based). Your database and clients will be happier.",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "OpenAPI Schema Customization",
        "content": "FastAPI's auto-generated OpenAPI schema is great, but sometimes you need to customize. Add examples, descriptions, and tags to make your docs shine.",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "Security Headers Matter",
        "content": "Add security headers to your responses: X-Content-Type-Options, X-Frame-Options, Content-Security-Policy. Small effort, big security improvement.",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
    {
        "title": "Caching Strategies",
        "content": "Not every request needs to hit the database. Use caching with Redis or even in-memory for frequently accessed data. Your response times will plummet (in a good way).",
        "channel": "SMS",
        "recipient": {
            "phone": "+59899123456"
        }
    },
    {
        "title": "GraphQL vs REST",
        "content": "GraphQL is trendy, but REST is battle-tested. Choose based on your needs, not hype. FastAPI excels at REST, but Strawberry brings GraphQL if you need it.",
        "channel": "PUSH",
        "recipient": {
            "token": "mQwh5w_ZuzDubMW4:jH3OB7k1UT-t8:zTewuorm3GvJ2.R-OMoADXyXiJvktElMT14-A6GOiPFpa0Ce4iP9IX3T.Sxj86E6_T"
        }
    },
    {
        "title": "Movie Quotes!",
        "content": "'You wanna know how I did it? This is how I did it, Anton. I never saved anything for the swim back.' - 'Gattaca'. One of my favorite movies of all time. That movie is actually one of the main reasons I decided to pursue an internship at NASA back in college. After that internship, I found I had a craving to learn and do more. It pushed me to take programming more seriously, which eventually led me to where I am today... Writing sample notifications at 3am. And you can too!",
        "channel": "EMAIL",
        "recipient": {
            "email": "recipient@example.com"
        }
    },
]

# The 44th notification - always the oldest (easter egg for testing pagination)
NOTIFICATION_44 = {
    "title": "Fun Fact: My High School Football Number Was #44",
    "content": "If you've paginated all the way to this notification, the 44th one... you get to learn this fun fact: that my high school football number was #44. Other notable absolute legends who wore number #44 include: Jerry West (NBA - Also fellow WV Native), Hank Aaron (MLB), and Floyd Little (NFL).",
    "channel": "EMAIL",
    "recipient": {
        "email": "contact_me@example.com"
    }
}


async def clear_existing_data() -> None:
    # Children first. Postgres enforces foreign keys, and a bulk delete() does
    # not follow the ORM's cascade, so every table that points at another must
    # be emptied before the table it points to.
    async with AsyncSessionLocal() as db:
        await db.execute(delete(models.DeliveryAttemptModel))
        await db.execute(delete(models.OutboxMessageModel))
        await db.execute(delete(models.NotificationModel))
        await db.execute(delete(models.PasswordResetTokenModel))
        await db.execute(delete(models.UserProfileModel))
        await db.execute(delete(models.UserModel))
        await db.commit()
    print("Cleared existing data")


async def update_notification_dates() -> None:
    now = datetime.now(UTC)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(models.NotificationModel).order_by(models.NotificationModel.id))
        notifications = result.scalars().all()

        if not notifications:
            return

        # First notification (NOTIFICATION_44) is the oldest - ~90 days ago
        await db.execute(
            update(models.NotificationModel)
            .where(models.NotificationModel.id == notifications[0].id)
            .values(created_at=now - timedelta(days=90)),
        )

        # Remaining notifications: each ~1.5 days newer than previous
        for i, notification in enumerate(notifications[1:], start=1):
            days_ago = (len(notifications) - i) * 1.5
            hours_offset = (i * 7) % 24
            notification_date = now - timedelta(days=days_ago, hours=hours_offset)
            await db.execute(
                update(models.NotificationModel)
                .where(models.NotificationModel.id == notification.id)
                .values(created_at=notification_date),
            )

        await db.commit()
    print("Updated notification dates")


async def populate() -> None:
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://localhost",
    ) as client:
        # Clear existing data (local images first, then database)
        await clear_existing_data()

        users: list[dict] = []

        print(f"\nCreating {len(USERS)} users...")
        for user_data in USERS:
            response = await client.post(
                "/api/users",
                json={
                    "email": user_data["email"],
                    "password": user_data["password"],
                },
            )
            response.raise_for_status()
            user = response.json()
            print(f"  Created: {user['email']}")

            response = await client.post(
                "/api/auth/token",
                data={
                    "username": user_data["email"],
                    "password": user_data["password"],
                },
            )
            response.raise_for_status()
            token = response.json()["access_token"]

            if profile := user_data.get("profile"):
                response = await client.patch(
                    f"/api/users/{user['id']}",
                        json={"profile": profile},
                        headers={"Authorization": f"Bearer {token}"},
                    )
                response.raise_for_status()
                print(f"    User has profile: {profile}")

            users.append(
                {"id": user["id"], "username": user["email"], "token": token},
            )

        print(f"\nCreating {len(NOTIFICATIONS) + 1} notifications...")

        # First create POST_44 (will become oldest after date update)
        response = await client.post(
            "/api/notifications",
            json={
                "title": NOTIFICATION_44["title"], 
                "content": NOTIFICATION_44["content"], 
                "channel": NOTIFICATION_44["channel"], 
                "recipient": NOTIFICATION_44["recipient"]
            },
            headers={"Authorization": f"Bearer {users[0]['token']}"},
        )
        response.raise_for_status()
        print(f"  Created: '{NOTIFICATION_44['title']}'")

        # Create remaining posts in reverse (last in list = oldest, first = newest)
        for i, notification_data in enumerate(reversed(NOTIFICATIONS)):
            user = users[i % len(users)]
            response = await client.post(
                "/api/notifications",
                json={
                    "title": notification_data["title"],
                    "content": notification_data["content"],
                    "channel": notification_data["channel"],
                    "recipient": notification_data["recipient"]
                },
                headers={"Authorization": f"Bearer {user['token']}"},
            )
            response.raise_for_status()
            title = notification_data["title"]
            print(
                f"  Created: '{title[:50]}...'"
                if len(title) > 50
                else f"  Created: '{title}'",
            )

        print("\nUpdating notification dates...")
        await update_notification_dates()

    await engine.dispose()

    print("\nDone!")
    print(f"  {len(USERS)} users")
    print(f"  {len(NOTIFICATIONS) + 1} notifications")


if __name__ == "__main__":
    # psycopg's async mode refuses Windows' default ProactorEventLoop; this is
    # the same reason alembic/env.py passes loop_factory.
    asyncio.run(populate(), loop_factory=asyncio.SelectorEventLoop)