# Oracle deployment

Run the validated deployment from the Oracle VM repository directory:

```bash
cd ~/apex-trader
bash scripts/deploy_oracle.sh
```

The script preserves the local `.env`, backs up paper state, pulls `origin/main`, configures risk defaults and the remote operator token, compiles and tests the active Python engine, builds and publishes the frontend, restarts the API and nginx, and runs the consolidated intelligence readiness report.

By default, Kyle remains stopped after deployment while the market is closed. To start the paper trader after a successful deployment:

```bash
START_TRADER=1 bash scripts/deploy_oracle.sh
```

The operator token printed at completion is required by the dashboard for remote control actions. Store it securely and never commit it.
