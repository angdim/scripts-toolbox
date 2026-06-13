# audio_peak_eq.py

`audio_peak_eq.py` автоматизира три аудио операции чрез FFmpeg:

1. Optional channel balance.
2. Optional EQ preset/custom EQ filters.
3. Final peak normalization до зададен target level.

## Работен поток

Когато са включени всички етапи, редът е:

```text
channel balance -> EQ -> peak normalization
```

Причина:

- `channel balance` коригира неравни канали в източника.
- `EQ` работи върху вече подравнена канална картина.
- `peak normalization` е последна, защото и balance, и EQ могат да променят максималния peak.

## Channel balance

Stereo режим:

```bash
audio_peak_eq.py -i input.wav -o output.wav -B --overwrite
```

Multi-channel режим:

```bash
audio_peak_eq.py -i input.mkv -o output.mkv -B --balance-mode all --overwrite
```

Параметри:

- `-B`, `--balance-channels`: включва channel balance.
- `--balance-mode stereo`: балансира само L/R и пропуска входове, които не са точно 2 канала.
- `--balance-mode all`: балансира всички канали към най-силния канал.
- `--balance-threshold 0.25`: минимална peak разлика в dB, над която се прилага корекция.

Алгоритъм:

1. Измерва peak на всеки канал поотделно.
2. Намира най-силния канал.
3. Усилва всеки по-слаб канал до нивото на най-силния, ако разликата е над прага.
4. Не намалява по-силния канал.

## EQ

Preset:

```bash
audio_peak_eq.py -i input.wav -o output.wav -p vocal_clarity --overwrite
```

Custom filter:

```bash
audio_peak_eq.py -i input.wav -o output.wav --eq-filter "equalizer=f=1000:t=q:w=1:g=2" --overwrite
```

## Peak normalization

Target peak:

```bash
audio_peak_eq.py -i input.wav -o output.wav -t -0.5 --overwrite
```

Финалната нормализация винаги се прави след channel balance и EQ, ако такива са заявени.

## Примери

Stereo balance + EQ + peak normalization:

```bash
audio_peak_eq.py -i input.wav -o output.wav -B -p vocal_clarity -t -0.5 --overwrite
```

Multi-channel balance + peak normalization:

```bash
audio_peak_eq.py -i movie.mkv -o movie_fixed.mkv -B --balance-mode all -t -1 --overwrite
```

Само peak normalization:

```bash
audio_peak_eq.py -i input.flac -o output.flac -t -0.5 --overwrite
```
