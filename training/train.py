"""
training/train.py - CLI driver for ES-MCCFR training on Short Deck PLO5.
"""

from __future__ import annotations

import sys
import os
import time
import argparse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from training.mccfr import MCCFRTrainer
from evaluator import warmup


def train(iterations: int = 5000, checkpoint_path: str = "assets/cfr_blueprint_v1.pkl",
          log_interval: int = 1000):
    print("=" * 70)
    print(f"STARTING ES-MCCFR TRAINING: {iterations} iterations")
    print(f"Checkpoint destination: {checkpoint_path}")
    print("=" * 70)

    warmup()
    trainer = MCCFRTrainer(seed=1337)
    start_time = time.perf_counter()

    for i in range(1, iterations + 1):
        trainer.train_iteration(match_seed="train_seed", deal_index=i)

        if i % log_interval == 0 or i == iterations:
            elapsed = time.perf_counter() - start_time
            rate = i / max(0.001, elapsed)
            num_infosets = len(trainer.strategy_sum)
            print(f"Iter {i:6d} / {iterations} | Time: {elapsed:6.1f}s | Speed: {rate:5.0f} it/s | InfoSets: {num_infosets:5d}")

    # Save final checkpoint
    trainer.save_checkpoint(checkpoint_path)
    print(f"\n[OK] Training complete. Saved checkpoint to {checkpoint_path}")
    print(f"Total InfoSets discovered: {len(trainer.strategy_sum)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--checkpoint", type=str, default="assets/cfr_blueprint_v1.pkl")
    parser.add_argument("--log-interval", type=int, default=1000)
    args = parser.parse_args()

    train(iterations=args.iterations, checkpoint_path=args.checkpoint, log_interval=args.log_interval)
