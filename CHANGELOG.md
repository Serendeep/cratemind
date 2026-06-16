# Changelog

## [0.2.0](https://github.com/Serendeep/cratemind/compare/v0.1.0...v0.2.0) (2026-06-16)


### Features

* add bpm analyzer, genre resolution and crate sorter ([36bcc35](https://github.com/Serendeep/cratemind/commit/36bcc3520ef43be26d8088f33e0fbb8186d8c1b9))
* add bpm, genre, template and manifest core ([dc59613](https://github.com/Serendeep/cratemind/commit/dc5961363e730556afce121451bb97b202739f42))
* add bundled-app pre-order cta to footer ([e6db31f](https://github.com/Serendeep/cratemind/commit/e6db31fee42b61147bbf40947de447d458ad8de1))
* add crate export and share-link from the ui ([e6b50e2](https://github.com/Serendeep/cratemind/commit/e6b50e29a520e9e7cc6945a93dad9a5fbf8616d5))
* add crate.json import to recreate a shared crate ([2055758](https://github.com/Serendeep/cratemind/commit/205575875f0ff03bfe162cba802aa23db6c95a05))
* add htmx ui with live progress and favicon ([78e9210](https://github.com/Serendeep/cratemind/commit/78e92100c4dce4ff4cc549ea719a45d73e52ba31))
* add progress bars and reconnect to the active run on reload ([01129f2](https://github.com/Serendeep/cratemind/commit/01129f262f75d2d979097ddecf80b21d8326193b))
* add run orchestrator and job manager ([8b788ae](https://github.com/Serendeep/cratemind/commit/8b788aeb24af9a18c91205b0384bbaf1965ae039))
* add spotdl and spotiflac download backends ([30ab6b2](https://github.com/Serendeep/cratemind/commit/30ab6b29b9d9fd3841b326d4749575646ddd9759))
* add sqlite store, manifest export and share upload ([d3f32d9](https://github.com/Serendeep/cratemind/commit/d3f32d9535a1d6cd043b387e9f844172c3973413))
* detect musical key and show it in camelot notation ([0d854f8](https://github.com/Serendeep/cratemind/commit/0d854f8f14fba2ca541646205f4684dc65fbce45))
* **download:** surface songs that fail to download in the UI ([48a993d](https://github.com/Serendeep/cratemind/commit/48a993d7a50b53882a4452c150e7f2e1c55c5b10))
* embed key, BPM and genre into downloaded file tags ([#3](https://github.com/Serendeep/cratemind/issues/3)) ([e95ceae](https://github.com/Serendeep/cratemind/commit/e95ceaef72db3332917786e92382cf3eb0f6f742))
* **genre:** classify from audio and drop the download cache ([1cabbba](https://github.com/Serendeep/cratemind/commit/1cabbbad98be1201b9784dfad4f479a6d7f6d913))
* **genre:** make the Deezer fallback opt-in and cache lookups ([fa46659](https://github.com/Serendeep/cratemind/commit/fa46659dd2c0d973ab6a696dc003b2115c43decb))
* remember last-used settings across runs ([e7e7479](https://github.com/Serendeep/cratemind/commit/e7e74794cf372e242d3d8098670046373e16fd77))
* self-update command and release-please CD ([#1](https://github.com/Serendeep/cratemind/issues/1)) ([7074557](https://github.com/Serendeep/cratemind/commit/70745571824d2fe46d546588b90e5a4a972d5008))
* **setup:** provision ffmpeg at runtime and pin spotdl to python 3.12 ([4390df0](https://github.com/Serendeep/cratemind/commit/4390df0a6e3a7d3a8a36cd69a401a80ad627245d))
* skip re-downloads with a cache and hardlink into the crate ([94a244d](https://github.com/Serendeep/cratemind/commit/94a244d63e97a1bf1e20b090697eb4884fa05964))
* **store:** persist the database and list past crates ([5d4eb15](https://github.com/Serendeep/cratemind/commit/5d4eb15faedd10eacaf8bd6475f13d2fa6527ba1))
* **web:** paginate the track list and tidy the crate summary ([c363f1a](https://github.com/Serendeep/cratemind/commit/c363f1a8c820ab9fd27356c7c69867a22568784a))
* **web:** show determinate download progress against playlist total ([816fd26](https://github.com/Serendeep/cratemind/commit/816fd263e330d6e7233d1ff3d9ba6f22217ffa38))


### Bug Fixes

* build spotdl output as a filename template not a dir ([c1b1827](https://github.com/Serendeep/cratemind/commit/c1b182748e915907cbd75b176e3719c9dc5dd2cb))
* correct spotiflac cli invocation to positional args ([ae8e601](https://github.com/Serendeep/cratemind/commit/ae8e601c8e8c39e16414c56aa4840d68b9971305))
* fall back to spotdl, pause lossless, show download progress ([77d75fb](https://github.com/Serendeep/cratemind/commit/77d75fb2ec6e3d74bb49df11e042fa8b3f4897b5))
* harden thread safety, octave window and subprocess errors ([140a7ff](https://github.com/Serendeep/cratemind/commit/140a7ff026b0306d4ce60310d0b8bf9b41d0cef7))
* label spotdl source as lossy instead of fallback ([483b7c8](https://github.com/Serendeep/cratemind/commit/483b7c89000f4674f133a322189647ca62286ef7))
* only mark spotiflac downloads as lossless ([0c57ae9](https://github.com/Serendeep/cratemind/commit/0c57ae95d692a35174a9c1ad0b4b55d0d31f4d5d))
* persist the camelot key in the store so resume keeps it ([bc86c07](https://github.com/Serendeep/cratemind/commit/bc86c075ef32bc0eb3e4d0cadf1e921098d941b0))
* poll while downloading and stream tool output to the terminal ([839e995](https://github.com/Serendeep/cratemind/commit/839e995f7ed44ba0ba92bedba99ac6fd0dcc29f1))
* resume from store and snapshot job tracks under lock ([4f51c48](https://github.com/Serendeep/cratemind/commit/4f51c48cbc9e4981013d2f29d2aec9063ad1cc2b))
* write cache to a dotless folder and process cached files on rerun ([acb60a3](https://github.com/Serendeep/cratemind/commit/acb60a32b621d6a238630f80edd78f72a068e614))


### Documentation

* add a screenshot to the readme ([1d638e9](https://github.com/Serendeep/cratemind/commit/1d638e9f662b0269035437e059702e6814f0f701))
* add readme, disclaimer, contributing and bug reporting ([331a454](https://github.com/Serendeep/cratemind/commit/331a454d2e65a2de30b704ecbd44583203c90a25))
* document setup script and the one-click app ([e357935](https://github.com/Serendeep/cratemind/commit/e357935cea3f2ec95c4c1fe5896539ddc56a35a0))
* drop readme em-dashes and correct the model size ([d77918c](https://github.com/Serendeep/cratemind/commit/d77918cf5c5dce93992a4760e831831690fca17f))
* lead with one-command setup and add a features overview ([2e0a8bd](https://github.com/Serendeep/cratemind/commit/2e0a8bdf61af1f2ed20f23d982c45f4862d9fa6a))
* reframe audio quality and roadmap lossless ([8cf2f1a](https://github.com/Serendeep/cratemind/commit/8cf2f1a6837257065372b1ebaa8935e8a55da493))
* reframe the one-click app pre-order pitch ([932d13a](https://github.com/Serendeep/cratemind/commit/932d13aaa2955d280d0beb9e350d1362401bcfa2))
* update README for the genre and setup changes ([273ed84](https://github.com/Serendeep/cratemind/commit/273ed84aabf9b17eea767ab192743fd82739c95e))
