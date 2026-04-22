# Release 250

- Kill stale Virtual Pilot node servers on app startup and before each VP start.
- Prevent stale port listeners on 3080/3300 from making VP look falsely ready.
- Track VP subprocess PIDs and clean them up on stop/restart.
- Keep VP status false until this app owns the running API and web processes.
