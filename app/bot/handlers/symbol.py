import json
from aiogram import Router, types
from aiogram.filters import Command
from app.core.nlp import load_symbols_from_json

router = Router()

@router.message(Command("symbol"))
async def cmd_symbol(message: types.Message):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Формат: /symbol <слово>\nНапример: /symbol змея")
        return
    query = args[1].strip().lower()

    symbols = load_symbols_from_json()
    # прямое совпадение ключа
    if query in symbols:
        info = symbols[query]
    else:
        # поиск по синонимам
        info = None
        for key, data in symbols.items():
            syns = [s.lower() for s in data.get("synonyms", [])] + [key.lower()]
            if query in syns:
                info = data
                info = {"_key": key, **data}
                break

    if not info:
        await message.answer("В словаре пока нет такого символа.")
        return

    key = info.get("_key") or query
    meaning = info.get("meaning", "—")
    actions = info.get("actions", []) or []

    text = (
        f"**Символ: {key}**\n"
        f"Значение: {meaning}\n\n" +
        ("Действия:\n" + "\n".join([f"• {a}" for a in actions]) if actions else "Действия: —")
    )
    await message.answer(text)
