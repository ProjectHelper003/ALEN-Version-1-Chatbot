# trainer.py
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from alen_env import ALENEnv
import os
import torch

def train_alen_rl_model():
    print("🔄 Initializing ALEN RL environment...")
    env = ALENEnv(dataset_path="interaction_dataset.json")
    check_env(env, warn=True)  # Optional sanity check

    # Automatically use GPU if available
    device = "cpu"
    print(f"🧠 Training PPO model on device: {device}")

    model_path = "alen_rl_model.zip"
    model = None

    if os.path.exists(model_path):
        print("📦 Loading existing model...")
        model = PPO.load(model_path, env=env, device=device)
    else:
        print("🆕 Creating new PPO model...")
        model = PPO("MlpPolicy", env, verbose=1, device=device)

    print("🚀 Starting training...")
    model.learn(total_timesteps=2000)
    print("💾 Saving model to alen_rl_model.zip")
    model.save(model_path)

if __name__ == "__main__":
    train_alen_rl_model()
