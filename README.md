# A2->T

**A2->T** — проект по разработке текстового императивного языка (расширенный псевдокод) и стенда для пакетных вычислительных экспериментов.

## Часть работы

Подсистема охватывает две основные задачи:

- `WATCHDOG` — динамический контроль выполнения алгоритма, отлов ошибок и ограничение числа тактов/операций;
- механизм прерывания пакетных прогонов по ограничению максимального числа операций для защиты от бесконечных циклов.

Реализованные в рамках этих задач элементы:

- `Watchdog`
- `StopCondition`
- `CounterManager`
- `TrialRunner`
- `RunResult`
- `RunStatus`
- `Stepper`
- `RoundRobinScheduler`
- batch interruption
- обработка `OK / LIMIT / ERROR`

## Структура проекта

```text
a2t/
  common/
  interpreter/
  integration/
  stand/
tests/
README.md
```

### Назначение директорий

- `common` — общие типы, ошибки и служебные структуры;
- `interpreter` — `watchdog`, счетчики, stop conditions, stepper;
- `integration` — интеграция семантического слоя с событиями выполнения;
- `stand` — runner, batch execution, scheduler, statistics, export;
- `tests` — модульные и интеграционные тесты.

## Как запускать

### Запуск тестов

```bash
python -m unittest tests/test.py
```

### Запуск demo

```bash
python demo.py
```



