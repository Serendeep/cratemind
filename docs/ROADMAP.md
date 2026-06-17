# Roadmap

Directional, not dated. It changes as we ship. Suggest or vote in an
[issue](https://github.com/Serendeep/cratemind/issues). cratemind stays free and open
source; the only planned paid thing is an optional one-click desktop app (same features).

### Done
- [x] Download a Spotify playlist and detect BPM, Camelot key, and genre per track
- [x] On-device genre model for underground electronic subgenres
- [x] Sort into folders you template (e.g. `hard techno/140-147/`)
- [x] Write key, BPM, and genre to tags for rekordbox, Serato, Mixxx
- [x] Live browser progress, instant resume, `crate.json` export/import
- [x] Genre aliases

### Now
- [ ] Sort music you already own (point at a local folder, skip the download)
- [ ] Dry-run preview before any files move
- [ ] Honest audio-quality tag (detect real bitrate, flag fake 320k upscales)

### Next
- [ ] Auto-resolve half/double BPM (174, not 87) and keep a crate tempo-consistent
- [ ] Auto energy score (1–10) with an `{energy}` template token
- [ ] Wider subgenre coverage + per-track confidence + shareable alias packs
- [ ] Published genre/key accuracy benchmark vs other tools

### Later
- [ ] Export to rekordbox and Engine DJ
- [ ] Per-track Bandcamp/Beatport buy links
- [ ] Duplicate detection (keep the best copy)
- [ ] Library health view (never-played, gaps) + local backup of analysis
- [ ] One-click code-signed desktop app

### Won't do
- No subscription, no cloud upload of your audio
- No automatic cue points or beatgrids
- No unreleased/promo redistribution

Contributions welcome, especially alias packs and template tokens. See the README's
Contributing section, and open an issue before anything large.
