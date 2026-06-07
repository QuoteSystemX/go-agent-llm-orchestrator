---
name: headroom-patterns
tags: [compression, tokens, performance, mcp, headroom, context]
description: Паттерны использования Headroom для сжатия контекста перед передачей в LLM. Сокращает потребление токенов на 60-95% без потери качества.
---

## Когда использовать headroom_compress

Вызывай `headroom_compress` ПЕРЕД добавлением в контекст LLM если:
- Вывод инструмента (grep, find, diff, log) > 200 токенов
- RAG-чанк или файл целиком > 300 токенов
- JSON-структура с повторяющимися полями > 150 токенов
- Стек-трейс или лог-файл любого размера

## Когда НЕ использовать

- Ответы пользователя — никогда не сжимай человеческий ввод
- Короткие результаты инструментов < 100 токенов
- Уже сжатые данные (compressed_id уже есть в объекте)
- Security-артефакты: пароли, ключи, токены авторизации

## Паттерн использования

```
# 1. Получить вывод инструмента
result = bash("grep -r 'pattern' src/")

# 2. Сжать перед передачей в контекст
compressed = headroom_compress(content=result, content_type="code")
# compressed = {compressed_id, compressed_content, token_savings_pct, original_tokens}

# 3. Использовать сжатый контент — LLM работает с ним как с оригиналом
# При необходимости LLM вызовет headroom_retrieve(compressed_id)

# 4. Bus-артефакты > 500 токенов — хранить compressed_id вместо full content
```

## Типы контента (content_type)

| Тип      | Когда применять                      | Компрессор                  |
|----------|--------------------------------------|-----------------------------|
| `code`   | Исходный код, diff, patch, stacktrace | CodeCompressor (AST-aware)  |
| `json`   | API-ответы, конфиги, логи в JSON     | SmartCrusher                |
| `text`   | Prose, документация, README          | Kompress-base               |
| `log`    | Лог-файлы, build output              | SmartCrusher + дедупликация |

## Получить статистику

```
headroom_stats() → {
  total_compressed: N,
  avg_savings_pct: 72.4,
  cache_hits: N,
  top_content_types: ["code", "json"]
}
```

## Восстановление оригинала

```
# LLM сам решает когда вызвать retrieve — обычно при детальном анализе
original = headroom_retrieve(compressed_id)
```

## Интеграция с Bus

Если bus-объект содержит поле `_ccr: true` — его content является сжатым.
Используй `pull_with_ccr(id, retrieve_full=True)` для получения оригинала.
