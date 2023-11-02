import json
import os
from typing import Optional

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from telegram import Update
from telegram.ext import Application, CallbackContext, CommandHandler, ContextTypes, MessageHandler, filters
from mongoengine import Document, connect, IntField, ListField, StringField, ReferenceField

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

class User(Document):
    user_id = IntField(unique=True, required=True)
    first_name = StringField()

# Define a MongoEngine document for Role
class Role(Document):
    name = StringField(unique=True, required=True)
    members = ListField(ReferenceField(User))


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
                                    '\n /out to stop getting tagged. '
                                    '\n /everyone to tag all that agreed to get tagged.'
                                    '\n /create_role <Role_name> to create a role (only for admins).'
                                    '\n /delete_role <Role_name> to delete a role (only for admins).'
                                    '\n /add_user_to_role <Role_name> reply to a user to '
                                    'add the user to a role (only for admins).'
                                    '\n /remove_user_from_role <Role_name> reply to a user to '
                                    'remove the user from a role (only for admins).'
                                    '\n /mention_role <Role_name> to mention users that has that role.'
                                    '\n /roles_info to list all available roles and their members.')


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

# Function to create a new role
async def create_role(update, context):
    chat_admins = await update.effective_chat.get_administrators()

    # Check if the user who sent the command is in the list of chat administrators
    is_admin = update.effective_user in (admin.user for admin in chat_admins)

    if is_admin:
        if context.args is not None and len(context.args) > 0:
            role_name = context.args[0]
            if not Role.objects(name=role_name):
                role = Role(name=role_name)
                role.save()
                await update.message.reply_text(f'Role {role_name} created.')
            else:
                await update.message.reply_text(f'Role {role_name} already exists.')
        else:
            await update.message.reply_text('Please provide a role name as an argument. create_role <Role_name> ')
    else:
        await update.message.reply_text('You are not authorized to perform this action.')


# Function to delete a role

async def delete_role(update, context):
    chat_admins = await update.effective_chat.get_administrators()

    # Check if the user who sent the command is in the list of chat administrators
    is_admin = update.effective_user in (admin.user for admin in chat_admins)

    if is_admin:
        if context.args is not None and len(context.args) > 0:
            role_name = context.args[0]
            role = Role.objects(name=role_name).first()
            if role:
                role.delete()
                await update.message.reply_text(f'Role {role_name} deleted.')
            else:
                await update.message.reply_text(f'Role {role_name} does not exist.')
        else:
            await update.message.reply_text('Please provide a role name as an argument. delete_role <Role_name> ')
    else:
        await update.message.reply_text('You are not authorized to perform this action.')


# Function to add a user to a role
async def add_user_to_role(update, context):
    chat_admins = await update.effective_chat.get_administrators()

    # Check if the user who sent the command is in the list of chat administrators
    is_admin = update.effective_user in (admin.user for admin in chat_admins)

    if context.args is not None and len(context.args) >= 1:
        role_name = context.args[0]

        # Check if the user has replied to a message
        if update.message.reply_to_message:
            user_id = update.message.reply_to_message.from_user.id
            user_first_name = update.message.reply_to_message.from_user.first_name  # Get the user's first name

            # Check if the user sending the command is an admin
            if is_admin:
                role = Role.objects(name=role_name).first()
                if role:
                    user = User.objects(user_id=int(user_id)).first()
                    if not user:
                        user = User(user_id=int(user_id), first_name=user_first_name)  # Store the first name
                        user.save()

                    if user not in role.members:
                        role.members.append(user)
                        role.save()
                        await update.message.reply_text(f'User {user_first_name} added to role {role_name}')  # Use the first name
                    else:
                        await update.message.reply_text(f'User {user_first_name} is already in role {role_name}')  # Use the first name
                else:
                    await update.message.reply_text(f'Role {role_name} does not exist.')
            else:
                await update.message.reply_text('You are not authorized to perform this action.')
        else:
            await update.message.reply_text('Please reply to a user to add them to a role.')
    else:
        await update.message.reply_text('Please provide a role name as an argument. add_user_to_role <Role_name> ')


# Function to remove a user from a role

async def remove_user_from_role(update, context):
    chat_admins = await update.effective_chat.get_administrators()

    # Check if the user who sent the command is in the list of chat administrators
    is_admin = update.effective_user in (admin.user for admin in chat_admins)

    if is_admin:
        # Check if the message is a reply to a user message
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            user_to_remove = update.message.reply_to_message.from_user

            if context.args is not None and len(context.args) >= 1:
                role_name = context.args[0]
                role = Role.objects(name=role_name).first()

                if role:
                    user = User.objects(user_id=user_to_remove.id).first()

                    if user and user in role.members:
                        # Remove the user from the role
                        role.members.remove(user)
                        role.save()

                        await update.message.reply_text(f'User {user_to_remove.first_name} removed from role {role_name}.')
                    else:
                        await update.message.reply_text(f'User {user_to_remove.first_name} is not in role {role_name}')
                else:
                    await update.message.reply_text(f'Role {role_name} does not exist.')
            else:
                await update.message.reply_text('Please provide a role name as an argument. remove_user_from_role <Role_name>')
        else:
            await update.message.reply_text('Please reply to a user message to remove them from the role.')
    else:
        await update.message.reply_text('You are not authorized to perform this action.')



# Function to mention users in a role
async def mention_role(update, context):
    if context.args is not None and len(context.args) > 0:
        role_name = context.args[0]
        role = Role.objects(name=role_name).first()
        if role:
            if role.members:  # Check if the role has members
                mentions = ', '.join([f"[{user.first_name}](tg://user?id={user.user_id})" for user in role.members])
                await update.message.reply_text(f'{mentions}', parse_mode="MarkdownV2")
            else:
                await update.message.reply_text(f'Role {role_name} has no members to mention.')
        else:
            await update.message.reply_text(f'Role {role_name} does not exist.')
    else:
        await update.message.reply_text('Please provide a role name as an argument. mention_role <Role_name>')



# Function to list all roles and their members
async def all_roles(update, context):
    roles = Role.objects()
    if roles:
        role_info = []
        for role in roles:
            member_names = []
            for user_ref in role.members:
                user = user_ref
                if user and hasattr(user, "first_name"):
                    member_names.append(user.first_name)
            role_info.append(f"Role {role.name}: {', '.join(member_names)}")
        response = '\n'.join(role_info)
        await update.message.reply_text(response)
    else:
        await update.message.reply_text('No roles exist.')



def register_application(application):
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("in", in_command))
    application.add_handler(CommandHandler("out", out_command))
    application.add_handler(CommandHandler("everyone", tag_command))
    application.add_handler(CommandHandler('create_role', create_role))
    application.add_handler(CommandHandler('delete_role', delete_role))
    application.add_handler(CommandHandler('add_user_to_role', add_user_to_role))
    application.add_handler(CommandHandler('remove_user_from_role', remove_user_from_role))
    application.add_handler(CommandHandler('mention_role', mention_role))
    application.add_handler(CommandHandler('roles_info', all_roles))
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, add_user_to_role))
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, remove_user_from_role))


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
