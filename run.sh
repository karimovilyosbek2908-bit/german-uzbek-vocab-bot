#!/usr/bin/env bash
# Botni fon rejimida ishga tushiradi. Log -> bot.log, PID -> bot.pid.
# Ikki marta ishga tushirishdan himoyalangan.
set -eu
cd "$(dirname "$0")"

PIDFILE="bot.pid"
LOGFILE="bot.log"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "Bot allaqachon ishlayapti (PID $(cat "$PIDFILE")). Avval ./stop.sh"
    exit 1
fi

PY="$(command -v python3 || command -v python)"
nohup "$PY" bot.py >> "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
sleep 2

if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "Bot ishga tushdi (PID $(cat "$PIDFILE")). Log: $LOGFILE"
    tail -n 5 "$LOGFILE" || true
else
    echo "Bot ishga tushmadi. Log:"
    tail -n 20 "$LOGFILE" || true
    rm -f "$PIDFILE"
    exit 1
fi
