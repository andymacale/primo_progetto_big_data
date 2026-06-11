#!/bin/bash

APP_PATH="/app/app.py"
PORT=80

start_app() {
    echo "Avvio di Streamlit sulla porta $PORT in background..."
    nohup python3 -B -m streamlit run /app/app.py --server.port 80 --server.address 0.0.0.0 > /tmp/streamlit.log 2>&1 &
}

stop_app() {
    echo "Arresto dell'applicazione Streamlit..."
    pkill -f "streamlit run"
    echo "App fermata."
}

status_app() {
    if pgrep -f "streamlit run" > /dev/null; then
        echo "L'applicazione è in ESECUZIONE."
    else
        echo "L'applicazione è FERMA."
    fi
}

case "$1" in
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    status)
        status_app
        ;;
    restart)
        stop_app
        sleep 2
        start_app
        ;;
    *)
        echo "Uso: $0 {start|stop|status|restart}"
        exit 1
esac