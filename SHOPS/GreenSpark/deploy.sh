#!/bin/bash
# Деплой парсера GreenSpark на серверы
# Запускать с локальной машины

set -e

# === КОНФИГУРАЦИЯ ===
SERVER_A="85.198.98.104"
SERVER_B="155.212.221.189"
SERVER_B_IP2="217.114.14.17"
USER="root"
REMOTE_PATH="/opt/parsers/GreenSpark"
LOCAL_PATH="$(dirname "$0")"

# === ФУНКЦИИ ===
deploy_to_server() {
    local server=$1
    local name=$2

    echo "=========================================="
    echo "Деплой на $name ($server)"
    echo "=========================================="

    # Создаём директорию
    ssh $USER@$server "mkdir -p $REMOTE_PATH/data $REMOTE_PATH/migrations"

    # Копируем файлы
    scp "$LOCAL_PATH/parser.py" $USER@$server:$REMOTE_PATH/
    scp "$LOCAL_PATH/coordinator.py" $USER@$server:$REMOTE_PATH/
    scp "$LOCAL_PATH/config.py" $USER@$server:$REMOTE_PATH/
    scp "$LOCAL_PATH/get_cookies.py" $USER@$server:$REMOTE_PATH/
    scp "$LOCAL_PATH/requirements.txt" $USER@$server:$REMOTE_PATH/
    scp "$LOCAL_PATH/data/greenspark_cities.json" $USER@$server:$REMOTE_PATH/data/
    scp "$LOCAL_PATH/migrations/001_parser_coordination.sql" $USER@$server:$REMOTE_PATH/migrations/

    # Копируем cookies если есть
    if [ -f "$LOCAL_PATH/cookies.json" ]; then
        scp "$LOCAL_PATH/cookies.json" $USER@$server:$REMOTE_PATH/
    fi

    # Устанавливаем зависимости
    ssh $USER@$server "cd $REMOTE_PATH && pip install -r requirements.txt"

    echo "Деплой на $name завершён!"
    echo ""
}

setup_db() {
    echo "=========================================="
    echo "Настройка БД (миграция координации)"
    echo "=========================================="

    ssh $USER@$SERVER_A "cd $REMOTE_PATH && PGPASSWORD='Mi31415926pSss!' psql -h localhost -p 5433 -U postgres -d db_greenspark -f migrations/001_parser_coordination.sql"

    echo "Миграция применена!"
    echo ""
}

register_servers() {
    echo "=========================================="
    echo "Регистрация серверов в координаторе"
    echo "=========================================="

    # Server A
    ssh $USER@$SERVER_A "cd $REMOTE_PATH && python coordinator.py --server server-a --register --ssh-command 'ssh root@$SERVER_A \"cd $REMOTE_PATH && python parser.py --coordinated --server server-a --incremental\"'"

    # Server B (с двумя IP для ротации)
    ssh $USER@$SERVER_A "cd $REMOTE_PATH && python coordinator.py --server server-b --register --ssh-command 'ssh root@$SERVER_B \"cd $REMOTE_PATH && python parser.py --coordinated --server server-b --incremental --ips $SERVER_B,$SERVER_B_IP2\"'"

    echo "Серверы зарегистрированы!"
    echo ""
}

add_cities() {
    echo "=========================================="
    echo "Добавление городов в очередь"
    echo "=========================================="

    ssh $USER@$SERVER_A "cd $REMOTE_PATH && python coordinator.py --add-cities"

    echo "Города добавлены!"
    echo ""
}

show_status() {
    echo "=========================================="
    echo "Статус очереди"
    echo "=========================================="

    ssh $USER@$SERVER_A "cd $REMOTE_PATH && python coordinator.py --status"
}

# === MAIN ===
case "${1:-all}" in
    deploy)
        deploy_to_server $SERVER_A "server-a"
        deploy_to_server $SERVER_B "server-b"
        ;;
    db)
        setup_db
        ;;
    register)
        register_servers
        ;;
    cities)
        add_cities
        ;;
    status)
        show_status
        ;;
    start-a)
        echo "Запуск парсера на server-a..."
        ssh $USER@$SERVER_A "cd $REMOTE_PATH && nohup python parser.py --coordinated --server server-a --incremental > parser.log 2>&1 &"
        echo "Парсер запущен! Лог: $REMOTE_PATH/parser.log"
        ;;
    start-b)
        echo "Запуск парсера на server-b..."
        ssh $USER@$SERVER_B "cd $REMOTE_PATH && nohup python parser.py --coordinated --server server-b --incremental --ips $SERVER_B,$SERVER_B_IP2 > parser.log 2>&1 &"
        echo "Парсер запущен! Лог: $REMOTE_PATH/parser.log"
        ;;
    log-a)
        ssh $USER@$SERVER_A "tail -f $REMOTE_PATH/parser.log"
        ;;
    log-b)
        ssh $USER@$SERVER_B "tail -f $REMOTE_PATH/parser.log"
        ;;
    all)
        deploy_to_server $SERVER_A "server-a"
        deploy_to_server $SERVER_B "server-b"
        setup_db
        register_servers
        add_cities
        show_status
        echo ""
        echo "=========================================="
        echo "ДЕПЛОЙ ЗАВЕРШЁН!"
        echo "=========================================="
        echo ""
        echo "Для запуска парсинга:"
        echo "  ./deploy.sh start-a    # запустить на server-a"
        echo "  ./deploy.sh start-b    # запустить на server-b"
        echo ""
        echo "Для мониторинга:"
        echo "  ./deploy.sh status     # статус очереди"
        echo "  ./deploy.sh log-a      # логи server-a"
        echo "  ./deploy.sh log-b      # логи server-b"
        ;;
    *)
        echo "Использование: $0 {deploy|db|register|cities|status|start-a|start-b|log-a|log-b|all}"
        exit 1
        ;;
esac
