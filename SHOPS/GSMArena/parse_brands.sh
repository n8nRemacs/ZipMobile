#!/bin/bash
cd /root/zipmobile/SHOPS/GSMArena

BRANDS="realme tecno infinix google oneplus"

for brand in $BRANDS; do
    echo "========================================"
    date
    echo "Parsing: $brand"
    echo "========================================"
    /usr/bin/python3 parser.py --brand "$brand"
    echo "Done $brand. Waiting 5 minutes..."
    sleep 300
done

date
echo "ALL DONE!"
