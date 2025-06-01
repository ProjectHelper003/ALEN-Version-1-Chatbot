import gymnasium as gym
from gymnasium import spaces
import numpy as np
import json
import os
from sentence_transformers import SentenceTransformer

class ALENEnv(gym.Env):
    def __init__(self, dataset_path="interaction_dataset.json", action_space_size=10):
        super(ALENEnv, self).__init__()
        self.dataset_path = dataset_path
        self.model = SentenceTransformer("multi-qa-MiniLM-L6-cos-v1")
        self.action_space = spaces.Discrete(action_space_size)
        self.observation_space = spaces.Box(low=-1, high=1, shape=(384,), dtype=np.float32)  # SentenceEmbedding size
        self.data = self._load_data()
        self.current_idx = 0
        self.action_lookup = self._build_action_lookup()

    def _load_data(self):
        if not self.dataset_path or not os.path.exists(self.dataset_path):
            return []
        with open(self.dataset_path, "r") as f:
            return json.load(f)

    def _build_action_lookup(self):
        unique_actions = list({item["action"] for item in self.data})
        return {i: act for i, act in enumerate(unique_actions)}

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_idx = np.random.randint(0, len(self.data))
        input_text = self.data[self.current_idx]["state"]
        encoded = self.model.encode(input_text)
        return np.array(encoded, dtype=np.float32), {}


    def step(self, action_idx):
        action_text = self.action_lookup.get(action_idx, "")
        real_action = self.data[self.current_idx]["action"]
        reward = 1 if action_text == real_action else -1

        terminated = True      # Episode ends after one step
        truncated = False      # Not terminated early
        info = {"chosen": action_text, "correct": real_action}

        state = self.model.encode(self.data[self.current_idx]["state"])
        return np.array(state, dtype=np.float32), reward, terminated, truncated, info

