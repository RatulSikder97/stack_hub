# Quarterly Voice Drift Gate

1. Re-run calibration on last 10 published posts vs 10 fresh corpus samples.
2. If detection >30%, voice has drifted.
3. Refresh `voice/voice_map.md` and `prompts/master_system_prompt.md`.
4. Do not publish new posts until calibration returns under 30%.
