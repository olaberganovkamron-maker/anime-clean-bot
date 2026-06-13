async def main():
    # Eski so‘rovlarni tozalash (ConflictError ni yo‘qotadi)
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)
