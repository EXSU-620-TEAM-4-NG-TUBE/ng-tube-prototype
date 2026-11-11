# Bench logs and database snapshots

| Folder | Source |
| --- | --- |
| [browser-monitor](browser-monitor/) | Browser monitor logs saved on the project computer |
| [stop-monitor](stop-monitor/) | Stop-monitor logs saved on the project computer |
| [home-bench-logs](home-bench-logs/) | Bench logs saved in the computer user folder |
| [earlier-archive](earlier-archive/) | Earlier evidence exports |
| [latest-update-archive](latest-update-archive/) | Latest-update evidence exports |
| [repository-browser-snapshot](repository-browser-snapshot/) | Browser logs previously stored in the software folder |

Each JSONL file preserves its source event stream. SQLite files are separate snapshots. Session IDs may recur across snapshots. The original database file at the top level is retained for earlier references. New live runs write to the monitor's working log directory.
