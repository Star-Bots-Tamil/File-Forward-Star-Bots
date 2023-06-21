from utils import temp_utils
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, UsernameInvalid, UsernameNotModified
from pyrogram.errors import FloodWait
from script import scripts
from vars import ADMINS, TARGET_DB, FILE_CAPTION
import asyncio
import re
import math, time
from datetime import datetime
from pytz import timezone
from script import scripts 
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
lock = asyncio.Lock()
CAPTION = {}

@Client.on_message(filters.command("start"))
async def start_message(bot, message):
    btn = [[
            InlineKeyboardButton("About", callback_data="about"),
            InlineKeyboardButton("Souce Code", callback_data="source")
        ],[
            InlineKeyboardButton("Close", callback_data="close"),
            InlineKeyboardButton("Help", callback_data="help")
        ]]
    await message.reply_text(
        text=scripts.START_TXT.format(message.from_user.mention, temp_utils.USER_NAME, temp_utils.BOT_NAME),
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(btn)
    )


@Client.on_message((filters.forwarded | (filters.regex("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text ) & filters.private & filters.incoming)
async def forward_cmd(bot, message):
    if message.from_user.id not in ADMINS: return # admin only
    if message.text:
        regex = re.compile("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(message.text)
        if not match:
            return await message.reply('Invalid link')
        source_chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if source_chat_id.isnumeric():
            source_chat_id  = int(("-100" + source_chat_id))
    elif message.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = message.forward_from_message_id
        source_chat_id = message.forward_from_chat.username or message.forward_from_chat.id
    else:
        return
    try:
        source_chat = await bot.get_chat(source_chat_id)
    except ChannelInvalid:
        return await message.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        logger.exception(e)
        return await message.reply(f'Errors - {e}')
    try:
        k = await bot.get_messages(source_chat_id, last_msg_id)
    except:
        return await message.reply('Make Sure That Iam An Admin In The Channel, if channel is private')
    if k.empty:
        return await message.reply('This may be group and iam not a admin of the group.')
    if lock.locked():
        return await message.reply_text('<b>Wait until previous process complete.</b>')        
    button = [[
        InlineKeyboardButton("Yes", callback_data=f"forward#{source_chat_id}#{last_msg_id}")
    ],[
        InlineKeyboardButton("No", callback_data="close")
    ]]
    await message.reply_text(
        text="**--Check Caption-- :- /set_caption to Check\n--Skip Messages-- :- /setskip To skip a Number of Messages\n\n\nDo you want to Start Forwarding ?**",
        reply_markup=InlineKeyboardMarkup(button)
    )

@Client.on_message(filters.command('logs') & filters.user(ADMINS))
async def log_file(bot, message):
    """Send log file"""
    try:
        await message.reply_document('Logs.txt')
    except Exception as e:
        await message.reply(str(e))


@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def skip_msgs(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try:
            skip = int(skip)
        except:
            return await message.reply("Skip number should be an integer.")
        await message.reply(f"Successfully set SKIP number as {skip}")
        temp_utils.CURRENT = int(skip)
    else:
        await message.reply("**Give me a Skip Number**")

@Client.on_message(filters.private & filters.command(['set_caption']))
async def set_caption(bot, message):
    try:
        caption = message.text.split(" ", 1)[1]
    except:
        return await message.reply("**Give me a caption.\n\nFile Caption Keys\n• `{filename}` :- Replaced by the Filename.\n• `{file_size}` :- Replaced by the Filesize.\n• `{caption}` :- Default File Caption ✍🏻**\n`/set_caption <b>{file_name}</b>`")
    CAPTION[message.from_user.id] = caption
    await message.reply(f"Successfully set file caption.\n\n{caption}")

async def start_forward(bot, userid, source_chat_id, last_msg_id):
    btn = [[
        InlineKeyboardButton("🚫 Cancel", callback_data="cancel_forward")
    ]]
    active_msg = await bot.send_message(
        chat_id=int(userid),
        text="<b>Starting Forward Process...</b>",
        reply_markup = InlineKeyboardMarkup(btn)
    ) 
    skipped = int(temp_utils.CURRENT)
    total = 0
    fetched = 0
    forwarded = 0
    empty = 0
    notmedia = 0
    unsupported = 0
    left = 0
    status = 'Idle'
    async with lock:
        try:
            btn = [[
                InlineKeyboardButton("🚫 Cancel", callback_data="cancel_forward")
            ]]
            status = 'Forwarding...'
            await active_msg.edit(
                text=f"<b>Forwarding on Progress...\n\nTotal :- <code>{total}</code>\nFetched :- <code>{fetched}</code>\nSkipped :- <code>{skipped}</code>\nForwarded :- <code>{forwarded}</code>\nEmpty Message :- <code>{empty}</code>\nNot Media :- <code>{notmedia}</code>\nUnsupported Media :- <code>{unsupported}</code>\nMessages Left :- <code>{left}</code>\n\nStatus :- {status}</b>",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            current = temp_utils.CURRENT
            temp_utils.CANCEL = False
            async for msg in bot.iter_messages(source_chat_id, int(last_msg_id), int(temp_utils.CURRENT)):
                if temp_utils.CANCEL:
                    status = 'Cancelled !'
                    await active_msg.edit(f"<b>Forward Cancelled!\n\nTotal :- <code>{total}</code>\nFetched :- <code>{fetched}</code>\nSkipped :- <code>{skipped}</code>\nForwarded :- <code>{forwarded}</code>\nEmpty Message :- <code>{empty}</code>\nNot Media :- <code>{notmedia}</code>\nUnsupported Media :- <code>{unsupported}</code>\nMessages Left :- <code>{left}</code>\n\nStatus :- {status}</b>")
                    break
                left = int(last_msg_id)-int(fetched)
                total = int(last_msg_id)
                fetched = current
                current += 1
                if current % 20 == 0:
                    btn = [[
                        InlineKeyboardButton("🚫 Cancel", callback_data="cancel_forward")
                    ]]
                    status = 'Sleeping for 60 Seconds.'
                    await active_msg.edit(
                        text=f"<b>Forwarding on Progress...\n\nTotal :- <code>{total}</code>\nFetched :- <code>{fetched}</code>\nSkipped :- <code>{skipped}</code>\nForwarded :- <code>{forwarded}</code>\nEmpty Message :- <code>{empty}</code>\nNot Media :- <code>{notmedia}</code>\nUnsupported Media :- <code>{unsupported}</code>\nMessages Left :- <code>{left}</code>\n\nStatus :- {status}</b>",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
                    await asyncio.sleep(60)
                    status = 'Forwarding...'
                    await active_msg.edit( 
                        text=f"<b>Forwarding on Progress...\n\nTotal :- <code>{total}</code>\nFetched :- <code>{fetched}</code>\nSkipped :- <code>{skipped}</code>\nForwarded :- <code>{forwarded}</code>\nEmpty Message :- <code>{empty}</code>\nNot Media :- <code>{notmedia}</code>\nUnsupported Media :- <code>{unsupported}</code>\nMessages Left :- <code>{left}</code>\n\nStatus :- {status}</b>", 
                        reply_markup=InlineKeyboardMarkup(btn) 
                    )
                if msg.empty:
                    empty+=1
                    continue
                elif not msg.media:
                    notmedia += 1
                    continue
                elif msg.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.DOCUMENT]:
                    unsupported += 1
                    continue
                media = getattr(msg, msg.media.value, None)
                if media.mime_type not in ['video/mp4', 'video/x-matroska']:  # Non mp4 and mkv files types skipping
                    unsupported += 1
                    continue
                try:
                    await msg.copy(
                        chat_id=int(TARGET_DB),
                        caption=FILE_CAPTION.format(file_name=media.file_name, file_size=get_size(media.file_size), caption=msg.caption)
                    )
                    forwarded+=1
                    await asyncio.sleep(1)
                except FloodWait as e:
                    btn = [[
                        InlineKeyboardButton("🚫 Cancel", callback_data="cancel_forward")
                    ]]
                    await active_msg.edit(
                        text=f"<b>Got FloodWait.\n\nWaiting for {e.value} Seconds.</b>",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
                except FloodWait as e:
                    await asyncio.sleep(e.value)  # Wait "value" seconds before continuing
                    await msg.copy(
                        chat_id=int(TARGET_DB),
                        caption=FILE_CAPTION.format(file_name=media.file_name, file_size=get_size(media.file_size), caption=msg.caption)
                    )
                    forwarded+=1
                    continue
            status = 'Completed !'
        except Exception as e:
            logger.exception(e)
            await active_msg.edit(f'<b>Forwarding Cancelled..\n\nTotal :- <code>{total}</code>\nFetched :- <code>{fetched}</code>\nSkipped :- <code>{skipped}</code>\nForwarded :- <code>{forwarded}</code>\nEmpty Message :- <code>{empty}</code>\nNot Media :- <code>{notmedia}</code>\nUnsupported Media :- <code>{unsupported}</code>\nMessages Left :- <code>{left}</code>\n\nStatus :- Cancelled !\n\nError :-</b> <code>{e}</code>')
        else:
            await active_msg.edit(f"<b>Successfully Completed Forward Process...!\n\nTotal :- <code>{total}</code>\nFetched :- <code>{fetched}</code>\nSkipped :- <code>{skipped}</code>\nForwarded :- <code>{forwarded}</code>\nEmpty Message :- <code>{empty}</code>\nNot Media :- <code>{notmedia}</code>\nUnsupported Media :- <code>{unsupported}</code>\nMessages Left :- <code>{left}</code>\n\nStatus :- {status}</b>")

def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])           

def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "D, ") if days else "") + \
        ((str(hours) + "H, ") if hours else "") + \
        ((str(minutes) + "M, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "") + \
        ((str(milliseconds) + "MS, ") if milliseconds else "")
    return tmp[:-2] 

def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60      
    return "%d:%02d:%02d" % (hour, minutes, seconds)
