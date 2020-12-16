# Import the async app instead of the regular one
from slack_bolt.async_app import AsyncApp

import logging

logging.basicConfig(level=logging.DEBUG)


app = AsyncApp()


@app.middleware  # or app.use(log_request)
async def log_request(logger, body, next):
    logger.debug(body)
    return await next()


@app.event("app_mention")
async def event_test(body, say, logger):
    logger.info(body)
    await say("What's up?")


@app.command("/backblast")
async def command(ack, body, respond):
    await ack()
    await respond(f"Hello <@{body['user_id']}>!")

if __name__ == "__main__":
    app.start(3000)
