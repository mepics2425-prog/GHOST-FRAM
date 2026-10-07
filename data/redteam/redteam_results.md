# GHOST FARM — CARS V2 Red-Team Robustness

Detector: frozen CARS V2

Evaluation positives: farm / mule / hub

Evaluation negatives: normal / hardcore / guild

Held-out unseen_02 reference F1@K: 0.923

      scenario  precision_at_k  recall_at_k  f1_at_k  f1_delta_vs_unseen02  baseline_f1_at_k  tp  fp  fn  tn  detected_farm  detected_mule  detected_hub  shadow_top_score  shadow_top_rank
   time_jitter           0.923        0.923    0.923                 0.000             0.538  12   1   1  19             10              2             0            48.610               10
    mule_split           0.769        0.769    0.769                -0.154             0.615  10   3   3  17              8              2             0            48.591                6
      micro_tx           0.923        0.923    0.923                 0.000             0.615  12   1   1  19             10              2             0            48.589               11
    normal_mix           0.846        0.846    0.846                -0.077             0.615  11   2   2  18              9              2             0            48.460                7
behavior_noise           0.923        0.923    0.923                 0.000             0.538  12   1   1  19             10              2             0            48.588               11
     composite           0.692        0.692    0.692                -0.231             0.692   9   4   4  16              7              2             0            48.535                7
