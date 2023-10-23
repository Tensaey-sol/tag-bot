import json
import os
from typing import Optional

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from telegram import Update
from telegram.ext import Application, CallbackContext, CommandHandler

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
TOKEN = os.getenv("YOUR_BOT_TOKEN")

app = FastAPI()
chat_users = {}

application = Application.builder().token(TOKEN).build()


class TelegramWebhook(BaseModel):
    update_id: int
    message: Optional[dict]
    edited_message: Optional[dict]
    channel_post: Optional[dict]
    edited_channel_post: Optional[dict]
    inline_query: Optional[dict]
    chosen_inline_result: Optional[dict]
    callback_query: Optional[dict]
    shipping_query: Optional[dict]
    pre_checkout_query: Optional[dict]
    poll: Optional[dict]
    poll_answer: Optional[dict]


async def start_command(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if chat_id not in chat_users:
        chat_users[chat_id] = {"with_usernames": [], "without_usernames": []}
    await update.message.reply_text(
        "Hello, I can help you mention friends! "
        "\n /in to agree to get tagged. "
        "\n /everyone to tag all that agreed to get tagged. "
        "\n /out to stop getting tagged."
    )


async def in_command(update: Update, context: CallbackContext):
    """Agree to be tagged in the group."""
    user = update.message.from_user
    user_id = user.id
    chat_id = update.message.chat_id
    if chat_id not in chat_users:
        chat_users[chat_id] = {"with_usernames": [], "without_usernames": []}

    # Check if the user is already in either list before adding them
    if user_id in [
        user.id for user in chat_users[chat_id]["with_usernames"]
    ] or user_id in [user.id for user in chat_users[chat_id]["without_usernames"]]:
        await update.message.reply_text("You are already in the tag list.")
    else:
        if user.username:
            chat_users[chat_id]["with_usernames"].append(user)
        else:
            chat_users[chat_id]["without_usernames"].append(user)
        await update.message.reply_text("You have agreed to be tagged in this group.")


async def out_command(update: Update, context: CallbackContext):
    """Remove a user from the tag list."""
    user = update.message.from_user
    user_id = user.id
    chat_id = update.message.chat_id
    if chat_id not in chat_users:
        chat_users[chat_id] = {"with_usernames": [], "without_usernames": []}

    if user_id in [user.id for user in chat_users[chat_id]["with_usernames"]]:
        chat_users[chat_id]["with_usernames"] = [
            u for u in chat_users[chat_id]["with_usernames"] if u.id != user_id
        ]
        await update.message.reply_text("You have been removed from the tag list.")
    elif user_id in [user.id for user in chat_users[chat_id]["without_usernames"]]:
        chat_users[chat_id]["without_usernames"] = [
            u for u in chat_users[chat_id]["without_usernames"] if u.id != user_id
        ]
        await update.message.reply_text("You have been removed from the tag list.")
    else:
        await update.message.reply_text("You were not in the tag list.")


async def tag_command(update: Update, context: CallbackContext):
    """Tag users who have agreed to be tagged in the group."""
    chat_id = update.message.chat_id
    if chat_id not in chat_users:
        chat_users[chat_id] = {"with_usernames": [], "without_usernames": []}

    if (
        not chat_users[chat_id]["with_usernames"]
        and not chat_users[chat_id]["without_usernames"]
    ):
        await update.message.reply_text("No users have agreed to be tagged yet.")
        return
    message = " ".join(context.args)

    # Mention users with usernames using "@" symbol
    mentioned_users_with_usernames = [
        f"@{user.username}" for user in chat_users[chat_id]["with_usernames"]
    ]

    # Mention users without usernames using Markdown format
    mentioned_users_without_usernames = [
        f"[{user.first_name}](tg://user?id={user.id})"
        for user in chat_users[chat_id]["without_usernames"]
    ]

    if mentioned_users_with_usernames:
        response_with_usernames = " ".join(mentioned_users_with_usernames)
        await update.message.reply_text(response_with_usernames)

    if mentioned_users_without_usernames:
        response_without_usernames = " ".join(mentioned_users_without_usernames)
        await update.message.reply_text(
            response_without_usernames, parse_mode="MarkdownV2"
        )


def register_application(application):
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("in", in_command))
    application.add_handler(CommandHandler("out", out_command))
    application.add_handler(CommandHandler("everyone", tag_command))


@app.post("/webhook")
async def webhook(webhook_data: TelegramWebhook):
    register_application(application)
    await application.initialize()
    await application.process_update(
        Update.de_json(
            json.loads(json.dumps(webhook_data.dict(), default=lambda o: o.__dict__)),
            application.bot,
        )
    )

    return {"message": "ok"}


@app.get("/")
def index():
    return {"message": "Hello World"}
