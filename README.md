# visualization

Интерактивный веб-дашборд для запуска псевдокода через интерпретатор и визуализации метрик алгоритмов (сравнения, обмены, присваивания и т.д.).

## Источники кода

| Папка в `src/` | Откуда взято | Описание |
|-----------------|-------------|----------|
| `src/demo/` | архив **demo** из чата | Парсер, CST-билдер, интерпретатор, грамматика, семантические обработчики |
| `src/generators/` | ветка **stand-generator** | Генераторы входных данных: random, sorted, reverse, nearly_sorted, duplicates |
| `src/event_bus.py` | ветка **visitor** (`src/common/events.py`) | Синхронная шина событий (pub/sub) |
| `src/event_collector.py` | собственный код | Сбор потока StepEvent с временными метками и снимками счётчиков |
| `src/stats_collector.py` | собственный код | Робастные статистики: mean, median, σ, IQR, квантили, CV |
| `src/counter_tracker.py` | собственный код | Накопление кумулятивных счётчиков операций |

## Структура

```
visualization/
├── dashboard.py          — точка входа: HTTP-сервер + HTML-дашборд
├── requirements.txt
├── README.md
└── src/
    ├── __init__.py
    ├── event_bus.py       — EventBus (pub/sub)
    ├── event_collector.py — EventCollector, RecordedStep
    ├── stats_collector.py — StatsCollector, RunResult, CounterStats
    ├── counter_tracker.py — CounterTracker
    ├── demo/              — интерпретатор псевдокода
    │   ├── bases/         — базовые модули (tokenizer, cstbuilder, interpretator)
    │   ├── cstbuilders/   — построение CST
    │   ├── interpretators/— генерированный интерпретатор
    │   ├── models/        — грамматика, узлы AST, токены
    │   ├── semantic_handlers/ — обработчики EBNF-грамматики
    │   ├── tokenizers/    — токенизатор RBNF
    │   └── visitor/       — EvalContext, реестр обработчиков
    └── generators/        — генераторы входных массивов
        ├── random_gen.py
        ├── sorted_gen.py
        ├── reverse_gen.py
        ├── nearly_sorted_gen.py
        └── duplicates_gen.py
```

## Как запустить

```bash
python dashboard.py
```

Дашборд откроется по адресу **http://127.0.0.1:8050**.

### Использование

1. Во вкладке **Editor** введите псевдокод алгоритма (или выберите пресет: BubbleSort / QuickSort).
2. Нажмите **+** чтобы добавить второй алгоритм для сравнения.
3. Укажите размеры массивов и количество прогонов, нажмите **Run Experiments**.
4. Результаты появятся на вкладках: **Overview**, **Complexity**, **Timeline**, **Compare**, **Raw Data**.

### Требования

- Python 3.10+
- Внешние pip-пакеты не требуются (только стандартная библиотека)
- Chart.js загружается из CDN в браузере
