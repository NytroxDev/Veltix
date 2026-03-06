# Logger

Veltix includes a production-ready logging system — singleton, thread-safe, colorized, with file rotation.

## Basic usage

```python
from veltix import Logger

logger = Logger.get_instance()

logger.trace("Very detailed info")
logger.debug("Debug info")
logger.info("General info")
logger.success("Operation successful")
logger.warning("Something to watch")
logger.error("Something went wrong")
logger.critical("Fatal error")
```

## Configuration

```python
from veltix import Logger, LoggerConfig, LogLevel
from pathlib import Path

config = LoggerConfig(
    level=LogLevel.DEBUG,
    enabled=True,
    use_colors=True,
    show_timestamp=True,
    show_caller=True,
    file_path=Path("logs/veltix.log"),
    file_rotation_size=10 * 1024 * 1024,  # 10 MB
    file_backup_count=5,
)

logger = Logger.get_instance(config)
```

## Log levels

| Level      | Severity |
|------------|----------|
| `TRACE`    | 5        |
| `DEBUG`    | 10       |
| `INFO`     | 20       |
| `SUCCESS`  | 25       |
| `WARNING`  | 30       |
| `ERROR`    | 40       |
| `CRITICAL` | 50       |

## Runtime controls

```python
logger.set_level(LogLevel.WARNING)  # change level
logger.disable()                    # mute all logs
logger.enable()                     # re-enable
stats = logger.get_stats()          # {LogLevel: count}
```
