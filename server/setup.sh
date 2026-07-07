#!/usr/bin/env bash
# One-time setup for the perception service. Run from the server/ folder.
set -e
cd "$(dirname "$0")"

# 1) get the CubiCasa model code + trained weights (once)
if [ ! -d CubiCasa5k/floortrans ]; then
  git clone https://github.com/CubiCasa/CubiCasa5k.git
fi
pip install gdown
gdown 1gRB7ez1e4H7a9Y09lLqRuna0luZO5VRK -O CubiCasa5k/model_best_val_loss_var.pkl

# 2) python packages
pip install -r requirements.txt

# 3) config
[ -f .env ] || cp .env.example .env

echo ""
echo "Setup done. Start the server with:"
echo "   uvicorn main:app --reload --port 8000"
