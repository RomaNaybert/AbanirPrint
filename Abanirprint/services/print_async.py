# services/print_async.py
import asyncio
from services.print_manager import print_and_wait
from services.decorators import notify_on_failure

@notify_on_failure("печать")
async def print_files_with_notification(bot, user_id, details, filepaths, copies=1):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, print_and_wait, filepaths, copies)