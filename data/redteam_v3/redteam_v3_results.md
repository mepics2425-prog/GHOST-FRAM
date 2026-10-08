# GHOST FARM — CARS V3 Red-Team Robustness

Detector: frozen CARS V3

Base snapshot: unseen_03

Evaluation positives: farm / mule / hub

Evaluation negatives: normal / hardcore / guild

Held-out unseen_03 reference F1@K: 1.000

      scenario  precision_at_k  recall_at_k  f1_at_k  f1_delta_vs_unseen03  cars_v2_f1_at_k  baseline_f1_at_k  tp  fp  fn  tn  detected_farm  detected_mule  detected_hub
   time_jitter             1.0          1.0      1.0                   0.0            0.923             0.538  13   0   0  20             10              2             1
    mule_split             1.0          1.0      1.0                   0.0            0.846             0.538  13   0   0  20             10              2             1
      micro_tx             1.0          1.0      1.0                   0.0            0.923             0.538  13   0   0  20             10              2             1
    normal_mix             1.0          1.0      1.0                   0.0            0.923             0.538  13   0   0  20             10              2             1
behavior_noise             1.0          1.0      1.0                   0.0            0.923             0.538  13   0   0  20             10              2             1
     composite             1.0          1.0      1.0                   0.0            0.846             0.538  13   0   0  20             10              2             1
