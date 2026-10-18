# shut-up-WH-1000XM4

Cathedral pipe-organ notification sounds to replace the spoken voice prompts
("Power on", "Bluetooth connected", …) of the Sony WH-1000XM4, plus notes from
installing them on a real unit running firmware 3.0.1.

This repository contains **no Sony audio, no encryption keys and no
decryption, repacking or flashing code**. It only provides original,
fully synthesized sounds and a write-up.

- Listen: [`sounds/preview.m4a`](sounds/preview.m4a)
  (power on → connected → disconnected → pairing → noise canceling → ambient sound → ambient sound off → power off)
- Sounds: [`sounds/`](sounds/) (48 kHz, mono, 64 kbps MP3, the same format as the headset's own prompts)
- Generator: [`generate.py`](generate.py)

## Why

The WH-1000XM4 speaks a sentence every time it powers on or off or a Bluetooth
device connects or disconnects. Turning off "Notification & Voice Guide" in the
Sound Connect app does not silence these: the app says that some important
notifications and guidance stay enabled, and power and connection prompts are
among them. I wanted short, AirPods-style cues instead, so I replaced the
prompts themselves.

## The sounds

Every sound is an additive-synthesis pipe organ (ranks at 16', 8', 4', 2 2/3'
and 2', a celeste rank, and a short wind "chiff" at the start of each note)
played into a synthetic cathedral reverb (RT60 2.4 s). Each sound is about 2
seconds long. No Sony audio is used.

| Sound | Replaces | Design |
|---|---|---|
| `power_on` | Power on | A C add9 chord built up from the lowest note across four octaves |
| `power_off` | Power off | The same chord falling from the top and settling on the low C |
| `connected` | Bluetooth connected, and the other "connected" prompts | A low G chord, then an upper voicing rises above it |
| `disconnected` | Bluetooth disconnected, and the other "disconnected" prompts | The upper voicing fades out, leaving only the low chord |
| `pairing` | Bluetooth pairing | A D chord pulsed three times |
| `noise_canceling_on` | Noise canceling | A low chord that darkens as if a swell box is closing: the outside world shuts out |
| `ambient_sound_on` | Ambient sound | A high flute chord that brightens and opens up: the room comes in |
| `ambient_sound_control_off` | Ambient Sound Control off | A single plain open fifth: neither state |
| (silence) | "Battery about XX%" right after power on | Not played |

The mapping from the headset's internal prompt slots to these sounds is the
`SLOTS` table in `generate.py`.

## Generating

```sh
uv run generate.py                  # regenerate sounds/
uv run generate.py --slots slots/   # also write prompt_NN.mp3 for each headset slot (24 files)
```

Requires [uv](https://docs.astral.sh/uv/) (or Python 3.10+ with numpy) and
ffmpeg built with `libmp3lame`. Timbre, reverb and length can be adjusted with
the constants at the top of `generate.py` and the sound definitions below them.

## Installing on the headset

This repository does not include any code or keys for decrypting, rebuilding
or writing the headset's voice-guidance pack. The work below by the community
made it possible. Follow each project's own license and warnings.

- [HelgeSverre/sony-vp-extract](https://github.com/HelgeSverre/sony-vp-extract): documents the voice-pack format
- [bsmith1698/sony-vp-extract](https://github.com/bsmith1698/sony-vp-extract): rebuilding packs and writing them over BLE
- [auracast-research/race-toolkit](https://github.com/auracast-research/race-toolkit) (ERNW): the Airoha RACE protocol
- [Jovlang/xm4-voice-studio](https://github.com/Jovlang/xm4-voice-studio) (fork of [SadsArches/xm4-voice-studio](https://codeberg.org/SadsArches/xm4-voice-studio/)): the install sequence derived from Sony's app
- [egaebel/sony-headphones-hack](https://github.com/egaebel/sony-headphones-hack): the earliest attempt

### Step by step

This is the procedure that worked for me on macOS with firmware 3.0.1. One
caveat: I rebuilt the pack with my own unpublished script, which makes the two
changes described in step 4. I have not run bsmith1698's `repack.py` with those
changes applied.

0. **Before you start**
   - Charge the headset to at least 50%.
   - In the Sound Connect app, set the voice-guidance language to **English**
     and check that the prompts are now in English. This makes the official
     English pack the one on the headset, which is also the pack you will
     modify and keep as a backup.
   - Quit Sound Connect and connect the headset to the Mac over Bluetooth.
   - Install [uv](https://docs.astral.sh/uv/) and ffmpeg.

1. **Clone the tools.** Put
   [bsmith1698/sony-vp-extract](https://github.com/bsmith1698/sony-vp-extract)
   and [auracast-research/race-toolkit](https://github.com/auracast-research/race-toolkit)
   side by side in the same folder. `push_voice_pack.py` looks for
   `race-toolkit` next to its own repository.

2. **Get and extract the English pack.** In `sony-vp-extract`, run
   `uv run extract_all.py`. It downloads the packs from Sony's server into
   `voice-packs/` and extracts them into `extracted/<language>/prompt_00.mp3` …
   `prompt_53.mp3`. Keep `voice-packs/VP_english_UPG_03.bin` unchanged as your
   backup.

3. **Put the new sounds in place.** In this repository, run
   `uv run generate.py --slots slots/`. Copy `extracted/english/` to a new
   folder, then copy the 24 files from `slots/` over it. The other 30 prompts,
   such as low-battery warnings, stay as Sony's voice.

4. **Rebuild the pack.** Build it from that folder with
   `uv run cli/repack.py --build <folder> <output.bin> voice-packs/VP_english_UPG_03.bin`,
   after making two changes to how `repack.py` builds the file:
   - **Checksum:** the first 32 bytes of the file must be the SHA-256 of
     everything from offset `0x100` to the end of the file, not from offset 32.
     Bytes 32 to `0xFF` are `0xFF` padding in Sony's files.
   - **Language code:** the first 32-bit word of the decompressed image (the
     `version` value that `repack.py` copies from the base pack) must be `4`
     (Spanish) instead of `1` (English). Otherwise the headset installs the
     pack but keeps playing its built-in English voice.

   Before writing anything, check the result: compute the SHA-256 of the
   output file from offset `0x100` and compare it with its first 32 bytes.

5. **Write it to the headset.** In `sony-vp-extract`, first run
   `uv run cli/push_voice_pack.py <output.bin>` without options. This is a dry
   run that only prints the plan. Then run it again with `--confirm` and type
   `yes`. The transfer takes about 3 to 4 minutes; keep the headset close to
   the Mac and do not turn it off.

6. **Check.** The script should end with `FotaCommit -> return_code=0`. The
   headset then reboots by itself and plays the new sounds. The app may now
   show the language as Spanish. Do not change it, because that reinstalls an
   official pack.

**To go back to Sony's voice:** change the voice-guidance language in the app.
The app installs the official pack for that language.

### Findings on firmware 3.0.1

1. **Packs labelled English are ignored.**
   If the language code at the start of the pack's image is English (`0x01`),
   the write and the commit both succeed and the headset reboots, but it keeps
   playing its built-in English voice. Even a stock Sony pack with only the
   "Power on" and "Power off" prompts swapped did not change anything.
   Labelling the pack Spanish (`0x04`), as xm4-voice-studio does, made it take
   effect.
2. **The checksum in the first 32 bytes of the file is `SHA-256(file[0x100:])`.**
   This matches the files Sony distributes, and xm4-voice-studio computes it the
   same way. The `repack.py` in bsmith1698's fork computes `SHA-256(file[32:])`
   instead, and the headset rejects packs built that way at the commit step.
   The commit failures that repository attributes to "stale CDN packs" are
   most likely caused by this difference: writing an unmodified pack from
   Sony's CDN committed successfully.
3. **On 3.0.1, RACE read commands are blocked but FOTA writes still work.**
   Flash reads, SDK info and build version queries were rejected or got no
   reply. The FOTA partition query and the write sequence still respond, and
   after the commit the headset reboots on its own and applies the pack.
4. **Changing the language in the app overwrites the pack.** To go back to
   Sony's voice, switch the language in the app and the official pack is
   installed again.
5. **Size:** the decompressed image is limited to 1 MB. With these ~2 s sounds
   in 24 slots it came to about 730 KB.

### Security note

Unauthenticated RACE access is the vulnerability ERNW reported
(CVE-2025-20700, CVE-2025-20701, CVE-2025-20702). In this test the pack was
written from a Mac that was already paired with the headset at the OS level.
Whether an unpaired third party could write to it was not tested.

## Disclaimer

- Use at your own risk. Modifying the headset may void the manufacturer's
  warranty, and writing to its flash can damage the device.
- Do not redistribute Sony's audio, voice packs containing it, or encryption
  keys.
- Sony and WH-1000XM4 are trademarks of their respective owners. This is an
  independent personal project and is not affiliated with Sony.

## License

- Code (`generate.py`): MIT License, see [`LICENSE`](LICENSE)
- Sounds (`sounds/`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
