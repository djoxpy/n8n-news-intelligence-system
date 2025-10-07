#!/usr/bin/env python3

import asyncio
import os
from telegram import Bot
from telegram.error import TelegramError
import json
from dotenv import load_dotenv

load_dotenv()

async def get_bot_info_and_updates(bot_token: str):
    try:
        bot = Bot(token=bot_token)

        print("🤖 Getting information about the bot...")

        bot_info = await bot.get_me()
        print(f"✅ Bot successfully connected!")
        print(f"📛 Bot name: {bot_info.first_name}")
        print(f"🏷️ Username: @{bot_info.username}")
        print(f"🆔 Bot ID: {bot_info.id}")

        print(f"\n" + "="*50)
        print("📬 GETTING UPDATES (CHAT IDs)")
        print("="*50)

        updates = await bot.get_updates(limit=100)

        if not updates:
            print("\n❌ No updates available!")
            print("\n💡 WHAT TO DO:")
            print("1. Send any message to the bot in a private message")
            print("2. Add the bot to the group and send a message to the group.")
            print("3. For forums/topics: send a message to a specific topic")
            print("4. Run this script again")
            return

        print(f"📨 {len(updates)} updates found\n")

        chats_info = {}
        threads_info = {}

        for update in updates:
            if update.message:
                chat = update.message.chat
                chat_id = chat.id
                message = update.message

                if chat_id not in chats_info:
                    chat_type = chat.type
                    is_channel = getattr(chat, 'is_channel', False)

                    if chat_type == 'supergroup' and is_channel:
                        chat_type = 'channel'

                    chat_info = {
                        'id': chat_id,
                        'type': chat_type,
                        'original_type': chat.type,
                        'is_channel': is_channel,
                        'title': chat.title if chat.title else 'No title',
                        'username': chat.username if chat.username else 'No username',
                        'first_name': chat.first_name if chat.first_name else 'No name',
                        'last_name': chat.last_name if chat.last_name else '',
                        'is_forum': getattr(chat, 'is_forum', False),
                        'messages_count': 0,
                        'threads': set()
                    }
                    chats_info[chat_id] = chat_info

                chats_info[chat_id]['messages_count'] += 1

                thread_id = message.message_thread_id
                if thread_id:
                    thread_key = (chat_id, thread_id)
                    chats_info[chat_id]['threads'].add(thread_id)

                    if thread_key not in threads_info:
                        thread_name = "Unknown thread"
                        if message.reply_to_message and message.reply_to_message.forum_topic_created:
                            thread_name = message.reply_to_message.forum_topic_created.name
                        elif message.is_topic_message:
                            thread_name = f"Thread #{thread_id}"

                        threads_info[thread_key] = {
                            'chat_id': chat_id,
                            'thread_id': thread_id,
                            'thread_name': thread_name,
                            'messages_count': 0
                        }

                    threads_info[thread_key]['messages_count'] += 1

        if chats_info:
            print("💬 FOUND CHATS:")
            print("-" * 70)

            for chat_id, info in chats_info.items():
                print(f"\n📍 Chat ID: {chat_id}")
                print(f"   Type: {info['type'].upper()}")

                if info.get('is_channel') and info['original_type'] == 'supergroup':
                    print(f"   📢 Channel (with threads)")

                if info['is_forum']:
                    print(f"   🗂️ FORUM (topic support): YES")

                if info['type'] == 'private':
                    name = f"{info['first_name']} {info['last_name']}".strip()
                    print(f"   👤 Name: {name}")
                    print(f"   🏷️ Username: @{info['username']}")

                elif info['type'] in ['group', 'supergroup']:
                    print(f"   👥 Group name: {info['title']}")
                    if info['username'] != 'No username':
                        print(f"   🏷️ Username: @{info['username']}")

                elif info['type'] == 'channel':
                    print(f"   📢 Channel name: {info['title']}")
                    if info['username'] != 'No username':
                        print(f"   🏷️ Username: @{info['username']}")
                    if info.get('is_channel') and info['original_type'] == 'supergroup':
                        print(f"   💬 Thread support: YES")

                print(f"   📊 Messages: {info['messages_count']}")

                if info['threads']:
                    print(f"   🧵 Found topics/threads: {len(info['threads'])}")
                    print(f"   📌 Thread IDs: {', '.join(map(str, sorted(info['threads'])))}")

                if info['type'] in ['group', 'supergroup']:
                    print(f"   ✅ FOR GROUP USE: chat_id={chat_id}")
                    if info['is_forum'] and info['threads']:
                        print(f"   ✅ FOR THREAD ADD: message_thread_id=<thread_id>")
                elif info['type'] == 'private':
                    print(f"   ✅ FOR PRIVATE MESAGGES: chat_id={chat_id}")
                elif info['type'] == 'channel':
                    print(f"   ✅ FOR CHANNEL USE: chat_id={chat_id}")
                    if info['threads']:
                        print(f"   ✅ FOR THREADS ADD: message_thread_id=<thread_id>")

        if threads_info:
            print(f"\n" + "="*70)
            print("🧵 DETAILED INFORMATION ABOUT TOPICS (THREADS):")
            print("-" * 70)

            for (chat_id, thread_id), thread_data in threads_info.items():
                chat_name = chats_info[chat_id]['title']
                print(f"\n📌 Topic: {thread_data['thread_name']}")
                print(f"   💬 Chat: {chat_name}")
                print(f"   🆔 Chat ID: {chat_id}")
                print(f"   🧵 Thread ID: {thread_id}")
                print(f"   📊 Messages in thread: {thread_data['messages_count']}")
                print(f"   ✅ Usage: chat_id={chat_id}, message_thread_id={thread_id}")

        output_data = {
            'bot_info': {
                'name': bot_info.first_name,
                'username': bot_info.username,
                'id': bot_info.id
            },
            'chats': {
                str(chat_id): {
                    **info,
                    'threads': list(info['threads'])
                }
                for chat_id, info in chats_info.items()
            },
            'threads': {
                f"{chat_id}_{thread_id}": thread_data
                for (chat_id, thread_id), thread_data in threads_info.items()
            },
            'timestamp': updates[-1].update_id if updates else None
        }

        with open('telegram_chats.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Information saved to file: telegram_chats.json")

        print(f"\n" + "="*50)
        print("💡 RECOMMENDATIONS:")
        print("="*50)

        group_chats = [chat_id for chat_id, info in chats_info.items()
                      if info['type'] in ['group', 'supergroup']]

        if group_chats:
            print(f"🎯 To send to a group, use one of these chat_id:")
            for chat_id in group_chats:
                chat_name = chats_info[chat_id]['title']
                is_forum = chats_info[chat_id]['is_forum']
                print(f"   • {chat_id} (group: {chat_name})")
                if is_forum:
                    print(f"     🗂️ FORUM: add message_thread_id to send to topic")
        else:
            print("❌ No group chats found.")
            print("📝 Ensure that:")
            print("   1. Bot added to group")
            print("   2. There are messages in the group after adding the bot.")
            print("   3. The bot has permission to read messages.")

        if threads_info:
            print(f"\n🧵 Found {len(threads_info)} FORUM topics ")
            print("📝 To post in the thread, use both parameters.:")
            print("   • chat_id")
            print("   • message_thread_id")

    except TelegramError as e:
        print(f"❌ Error Telegram API: {e}")
        if "Unauthorized" in str(e):
            print("💡 Verify the correctness of the bot token")
        elif "Bad Request" in str(e):
            print("💡 Check the token format")

    except Exception as e:
        print(f"💥 Unexpected error: {e}")

async def get_channel_info(bot_token: str, channel_username: str):
    try:
        bot = Bot(token=bot_token)

        print(f"🔍 Search for information about the channel @{channel_username}...")

        bot_info = await bot.get_me()

        chat = await bot.get_chat(f"@{channel_username}")

        print(f"\n✅ Channel found!")
        print(f"📍 Chat ID: {chat.id}")
        print(f"📢 Name: {chat.title}")
        print(f"🏷️ Username: @{chat.username}")
        print(f"   Type: {chat.type.upper()}")

        if hasattr(chat, 'description') and chat.description:
            print(f"📝 Description: {chat.description[:100]}...")

        try:
            member = await bot.get_chat_member(chat.id, bot_info.id)
            print(f"\n🤖 Bot status in the channel: {member.status}")

            if member.status == 'administrator':
                print("✅ The bot is an administrator.")
                if hasattr(member, 'can_post_messages'):
                    print(f"   📝 Can post: {member.can_post_messages}")
                if hasattr(member, 'can_edit_messages'):
                    print(f"   ✏️ Can edit: {member.can_edit_messages}")
                if hasattr(member, 'can_delete_messages'):
                    print(f"   🗑️ Can delete: {member.can_delete_messages}")
        except Exception as e:
            print(f"⚠️ Unable to verify permissions: {e}")

        print(f"\n✅ USE: chat_id={chat.id}")

        return chat.id

    except TelegramError as e:
        print(f"❌ Error: {e}")
        if "chat not found" in str(e).lower():
            print("💡 Check:")
            print("   1. The channel username is entered correctly (without @)")
            print("   2. The channel is public or the bot has been added as an administrator")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")

async def clear_updates(bot_token: str):
    try:
        bot = Bot(token=bot_token)

        print("🧹 Cleaning up old updates...")

        updates = await bot.get_updates(limit=100)

        if not updates:
            print("✅ No updates for cleaning")
            return

        last_update_id = updates[-1].update_id

        await bot.get_updates(offset=last_update_id + 1, limit=1)

        print(f"✅ Cleaned up {len(updates)} old updates")
        print(f"💡 Now only new messages will be displayed.")

    except TelegramError as e:
        print(f"❌ Cleanup error: {e}")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")

async def send_test_message(bot_token: str, chat_id: str, thread_id: str = None):
    try:
        bot = Bot(token=bot_token)

        test_message = """🧪 Test message from news aggregator!

✅ If you see this message, the settings are correct.

🤖 Automatic news reports will soon be appearing here."""

        send_params = {
            'chat_id': chat_id,
            'text': test_message
        }

        if thread_id:
            send_params['message_thread_id'] = int(thread_id)
            print(f"🧵 Send to topic (thread_id: {thread_id})...")

        message = await bot.send_message(**send_params)
        print(f"✅ Test message sent successfully!")
        print(f"📬 Message ID: {message.message_id}")
        if thread_id:
            print(f"🧵 Thread ID: {thread_id}")

    except TelegramError as e:
        print(f"❌ Error sending message: {e}")
        if "chat not found" in str(e):
            print("💡 Check the correctness of chat_id")
        elif "bot was blocked" in str(e):
            print("💡 Bot blocked by user")
        elif "not enough rights" in str(e):
            print("💡 The bot does not have permission to send messages to this chat.")
        elif "thread not found" in str(e) or "message thread not found" in str(e):
            print("💡 Topic (thread) not found. Check message_thread_id")
        elif "TOPIC_CLOSED" in str(e):
            print("💡 Topic closed. Open it or select another one.")

def main():
    print("🔍 DEFINE TELEGRAM CHAT_ID AND THREAD_ID")
    print("="*50)

    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')

    if not bot_token:
        print("❌ The TELEGRAM_BOT_TOKEN environment variable is not set.")
        bot_token = input("🤖 Enter the bot token (from @BotFather): ").strip()

    if not bot_token:
        print("❌ Token not specified. Terminating.")
        return

    print(f"🔑 Token used: {bot_token[:10]}...{bot_token[-10:]}")

    print(f"\n📋 SELECT ACTION:")
    print("1. Find all chat_id and thread_id from messages")
    print("2. Get the chat_id of a channel by username")
    print("3. Send a test message (to chat/channel)")
    print("4. Send a test message (topic)")
    print("5. Clear old updates (delete cache)")

    try:
        choice = input("\n➡️ Your choice (1-5): ").strip()

        if choice == "1":
            asyncio.run(get_bot_info_and_updates(bot_token))

        elif choice == "2":
            channel_username = input("🏷️ Enter the channel username (without @): ").strip()
            if channel_username:
                channel_username = channel_username.lstrip('@')
                asyncio.run(get_channel_info(bot_token, channel_username))
            else:
                print("❌ Username not specified")

        elif choice == "3":
            chat_id = input("💬 Enter chat_id for testing: ").strip()
            if chat_id:
                asyncio.run(send_test_message(bot_token, chat_id))
            else:
                print("❌ Chat ID not specified")

        elif choice == "4":
            chat_id = input("💬 Enter chat_id: ").strip()
            thread_id = input("🧵 Enter message_thread_id: ").strip()
            if chat_id and thread_id:
                asyncio.run(send_test_message(bot_token, chat_id, thread_id))
            else:
                print("❌ Chat ID or Thread ID not specified")

        elif choice == "5":
            print("\n⚠️ WARNING: This will delete all unread updates.!")
            confirm = input("Continue? (yes/no): ").strip().lower()
            if confirm in ['yes', 'y']:
                asyncio.run(clear_updates(bot_token))
            else:
                print("❌ Cancelled")

        else:
            print("❌ Wrong choice")

    except KeyboardInterrupt:
        print("\n👋 Terminating...")
    except Exception as e:
        print(f"💥 Error: {e}")

if __name__ == '__main__':
    main()
