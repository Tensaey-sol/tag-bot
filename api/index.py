import json
import os
from typing import Optional

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from telegram import Update
from telegram.ext import Application, CallbackContext, CommandHandler
from mongoengine import Document, connect, IntField, ListField

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
TOKEN = os.getenv("YOUR_BOT_TOKEN")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_URL = os.getenv("MONGO_URL")

if MONGO_PASSWORD and MONGO_URL:
    MONGO_URL = MONGO_URL.replace('<password>', MONGO_PASSWORD)
    connect(host=MONGO_URL)

app = FastAPI()

#Intialize a class to store data on the database

class ChatUser(Document):
    chat_id = IntField(primary_key=True)
    with_usernames = ListField()
    without_usernames = ListField()


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


async def check_user(chat_id):
    chat_user = ChatUser.objects(chat_id=chat_id).first()
    if not chat_user:
        chat_user = ChatUser(chat_id=chat_id)
        chat_user.save()
    return chat_user

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text('Hello, I can help you mention friends! '
                                    '\n /in to agree to get tagged. '
                                    '\n /everyone to tag all that agreed to get tagged. '
                                    '\n /out to stop getting tagged.')


async def in_command(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    user_firstname = update.message.from_user.first_name

    chat_user = await check_user(chat_id)  # Await the asynchronous function

    if username:
        # User has a username, add to with_usernames list
        if username in chat_user.with_usernames:
            await update.message.reply_text("You are already in the list.")
        else:
            chat_user.with_usernames.append(username)
            chat_user.save()
            await update.message.reply_text("You have agreed to be tagged.")
    else:
        # User does not have a username, add to without_usernames list
        if str(user_id) in chat_user.without_usernames:
            await update.message.reply_text("You are already in the list.")
        else:
            # Store user_id and user_firstname
            user_info = {'user_id': user_id, 'user_firstname': user_firstname}
            chat_user.without_usernames.append(user_info)
            chat_user.save()
            await update.message.reply_text("You have agreed to be tagged.")




async def out_command(update: Update, context: CallbackContext):
    """Remove a user from the tag list."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    user_id = user.id
    username = user.username

    # Check if the user data exists
    chat_user = await check_user(chat_id)  # Await the asynchronous function

    if chat_user:
        if username in chat_user.with_usernames:
            chat_user.with_usernames.remove(username)
            chat_user.save()
            await update.message.reply_text('You have been removed from the tag list.')
        elif any(user_id == user_info['user_id'] for user_info in chat_user.without_usernames):
            chat_user.without_usernames = [user_info for user_info in chat_user.without_usernames if user_id != user_info['user_id']]
            chat_user.save()
            await update.message.reply_text('You have been removed from the tag list.')
        else:
            await update.message.reply_text('You were not in the tag list.')
    else:
        # Handle the case where user data doesn't exist.
        await update.message.reply_text('Chat user data not found.')


async def tag_command(update: Update, context: CallbackContext):
    """Tag users who have agreed to be tagged in the group."""
    chat_id = update.message.chat_id

    # Retrieve user data from the MongoDB database
    chat_user = await check_user(chat_id)  # Await the asynchronous function

    if chat_user:
        if not chat_user.with_usernames and not chat_user.without_usernames:
            await update.message.reply_text('No users have agreed to be tagged yet.')
            return

        message = ' '.join(context.args)

        # Mention users with usernames using "@" symbol
        mentioned_users_with_usernames = [f"@{username}" for username in chat_user.with_usernames]

        # Mention users without usernames using Markdown format
        mentioned_users_without_usernames = [
            f"[{user['user_firstname']}](tg://user?id={user['user_id']})" for user in chat_user.without_usernames
        ]


        if mentioned_users_with_usernames:
            response_with_usernames = ' '.join(mentioned_users_with_usernames)
            await update.message.reply_text(response_with_usernames)

        if mentioned_users_without_usernames:
            response_without_usernames = ' '.join(mentioned_users_without_usernames)
            await update.message.reply_text(response_without_usernames, parse_mode="MarkdownV2")
    else:
        # Handle the case where user data doesn't exist.
        await update.message.reply_text('Chat user data not found.')



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
