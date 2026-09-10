#!/usr/bin/env bash
# Fon rejimida ishlayotgan botni to'xtatadi (bot.pid bo'yicha).
set -eu
cd "$(dirname "$0")"

PIDFILE="bot.pid"
if [ ! -f "$PIDFILE" ]; then
    echo "bot.pid topilmadi. Bot ishlamayapti (yoki ./run.sh orqali boshlanmagan)."
    # ehtiyot chorasi: nomi bo'yicha ham urinib ko'ramiz
    pkill -f "python.* bot.py" 2>/dev/null && echo "Nomi bo'yicha to'xtatildi." || true
    exit 0
fi

PID="$(cat "$PIDFILE")"
if kill "$PID" 2>/dev/null; then
    echo "To'xtatildi (PID $PID)."
else
    echo "PID $PID allaqachon o'lik."
fi
rm -f "$PIDFILE"
