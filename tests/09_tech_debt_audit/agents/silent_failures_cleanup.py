import os
import subprocess


def log_replacement(file_path: str, old_str: str, new_str: str) -> bool:
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    if old_str not in content:
        print(f"Pattern not found in {file_path}")
        return False

    new_content = content.replace(old_str, new_str)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"Successfully patched {file_path}")
    return True

def main():
    print("Starting automated cleanup of 5 silent failures...")

    # 1. src/bot/preflight.py
    # Inject imports if needed and replace the admin alert failure with a printed log/print_status
    preflight_old = """    except Exception:
        pass"""

    preflight_new = """    except Exception as e:
        # Preflight doesn't import standard logger, uses stdout/stderr helpers
        import sys
        print(f"[ERROR] Failed to send admin alert: {e}", file=sys.stderr)"""

    # 2. src/bot/intake.py
    # Replace parser exception in _format_session_summary with structured logger warning
    intake_old = """            except (ValueError, TypeError):
                pass"""

    intake_new = """            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse birth datetime for UI: {parsed_dob_str} - Error: {e}")"""

    # 3, 4, 5. src/bot/chronomancer_handler.py
    # Replace date parsing exceptions with debug logging
    chrono_old_1 = """        try:
            dates.append(dt.strptime(match.group(1), "%Y-%m-%d").date())
        except ValueError:
            pass"""

    chrono_new_1 = """        try:
            dates.append(dt.strptime(match.group(1), "%Y-%m-%d").date())
        except ValueError as e:
            logger.debug(f"Regex extracted invalid ISO date string: {match.group(1)} - Error: {e}")"""

    chrono_old_2 = """        try:
            dates.append(date(FORECAST_YEAR, month, day))
        except ValueError:
            pass"""

    chrono_new_2 = """        try:
            dates.append(date(FORECAST_YEAR, month, day))
        except ValueError as e:
            logger.debug(f"Regex extracted invalid month day date: {FORECAST_YEAR}-{month}-{day} - Error: {e}")"""

    # Apply changes
    log_replacement("src/bot/preflight.py", preflight_old, preflight_new)
    log_replacement("src/bot/intake.py", intake_old, intake_new)
    log_replacement("src/bot/chronomancer_handler.py", chrono_old_1, chrono_new_1)
    # The monthly regex uses identical structure twice, replace all occurrences of second pattern
    log_replacement("src/bot/chronomancer_handler.py", chrono_old_2, chrono_new_2)

    print("\nRunning linter check...")
    res = subprocess.run(["uv", "run", "ruff", "check", "src/bot/"], capture_output=True, text=True)
    if res.returncode == 0:
        print("Linter checks passed cleanly!")
    else:
        print("Linter issues found:")
        print(res.stdout)
        print(res.stderr)

if __name__ == "__main__":
    main()
