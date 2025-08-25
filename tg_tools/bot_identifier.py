#!/usr/bin/env python3

import asyncio
import os
from telegram import Bot
from telegram.error import TelegramError
import json

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
            print("3. Run this script again")
            return

        print(f"📨 {len(updates)} updates found\n")

        chats_info = {}

        for update in updates:
            if update.message:
                chat = update.message.chat
                chat_id = chat.id

                if chat_id not in chats_info:
                    chat_info = {
                        'id': chat_id,
                        'type': chat.type,
                        'title': chat.title if chat.title else 'No title',
                        'username': chat.username if chat.username else 'No username',
                        'first_name': chat.first_name if chat.first_name else 'No name',
                        'last_name': chat.last_name if chat.last_name else '',
                        'messages_count': 0
                    }
                    chats_info[chat_id] = chat_info

                chats_info[chat_id]['messages_count'] += 1

        if chats_info:
            print("💬 FOUND CHATS:")
            print("-" * 70)

            for chat_id, info in chats_info.items():
                print(f"\n📍 Chat ID: {chat_id}")
                print(f"   Type: {info['type'].upper()}")

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

                print(f"   📊 Messages: {info['messages_count']}")

                if info['type'] in ['group', 'supergroup']:
                    print(f"   ✅ FOR GROUPS USE: {chat_id}")
                elif info['type'] == 'private':
                    print(f"   ✅ FOR PERSONAL MESSAGES: {chat_id}")
                elif info['type'] == 'channel':
                    print(f"   ✅ USE FOR CHANNEL: {chat_id}")

        output_data = {
            'bot_info': {
                'name': bot_info.first_name,
                'username': bot_info.username,
                'id': bot_info.id
            },
            'chats': chats_info,
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
                print(f"   • {chat_id} (group: {chat_name})")
        else:
            print("❌ No group chats found.")
            print("📝 Ensure that:")
            print("   1. Bot added to group")
            print("   2. There are messages in the group after adding the bot.")
            print("   3. The bot has permission to read messages.")

    except TelegramError as e:
        print(f"❌ Error Telegram API: {e}")
        if "Unauthorized" in str(e):
            print("💡 Verify the correctness of the bot token")
        elif "Bad Request" in str(e):
            print("💡 Check the token format")

    except Exception as e:
        print(f"💥 Unexpected error: {e}")

async def send_test_message(bot_token: str, chat_id: str):
    try:
        bot = Bot(token=bot_token)

        test_message = """🧪 Test message from news aggregator!

✅ If you see this message, then chat_id is configured correctly.

🤖 Automatic news reports will soon be appearing here."""

        message = await bot.send_message(chat_id=chat_id, text=test_message)
        print(f"✅ Test message sent successfully!")
        print(f"📬 Message ID: {message.message_id}")

    except TelegramError as e:
        print(f"❌ Error sending message: {e}")
        if "chat not found" in str(e):
            print("💡 Check the correctness of chat_id")
        elif "bot was blocked" in str(e):
            print("💡 Bot blocked by user")
        elif "not enough rights" in str(e):
            print("💡 The bot does not have permission to send messages in this chat.")

def main():
    print("🔍 DEFINE TELEGRAM CHAT_ID")
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
    print("1. Find all chat_id (recommended)")
    print("2. Send a test message")

    try:
        choice = input("\n➡️ Your choice (1-2): ").strip()

        if choice == "1":
            asyncio.run(get_bot_info_and_updates(bot_token))

        elif choice == "2":
            chat_id = input("💬 Enter chat_id for testing: ").strip()
            if chat_id:
                asyncio.run(send_test_message(bot_token, chat_id))
            else:
                print("❌ Chat ID not specified")
        else:
            print("❌ Wrong choice")

    except KeyboardInterrupt:
        print("\n👋 Terminating...")
    except Exception as e:
        print(f"💥 Error: {e}")

if __name__ == '__main__':
    main()
