#!/bin/bash

cd "$(dirname "$0")"

python3 -m venv venv
source venv/bin/activate

pip install -q -r requirements.txt

export KMP_DUPLICATE_LIB_OK=TRUE
python book_ui.py
