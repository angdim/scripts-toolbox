# audio_peak_eq.py

`audio_peak_eq.py` автоматизира няколко аудио операции чрез FFmpeg:

1. Optional channel balance.
2. Optional EQ preset/custom EQ filters.
3. Optional silence analysis и trim/compress на дълги паузи.
4. Final peak или loudness normalization.

## Работен поток

Когато са включени всички етапи, редът е:

```text
channel balance -> EQ/filters -> silence trim -> final normalization
```

Причина:

- `channel balance` коригира неравни канали в източника.
- `EQ` работи върху вече подравнена канална картина.
- `silence trim` скъсява времевата структура след тоналните корекции.
- финалната нормализация е последна, защото предишните етапи могат да променят peak, loudness и общата продължителност.

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

## Silence analysis и trim

Само анализ на паузите, без изходен файл:

```bash
audio_peak_eq.py -i input.wav --analyze-silence --silence-threshold -45 --silence-duration 2
```

Изрязване/скъсяване на паузи по-дълги от зададен праг:

```bash
audio_peak_eq.py -i input.wav -o trimmed.wav --trim-silence --silence-threshold -45 --silence-duration 2 --keep-silence 0.4 --overwrite
```

Параметри:

- `--trim-silence`: включва FFmpeg `silenceremove` етапа.
- `--analyze-silence`: извежда start/end/duration отчет за паузите, без обработка.
- `--silence-trim-engine auto`: избира `silenceremove` за прост audio trim и `concat` при fade/crossfade или видео.
- `--silence-threshold -45`: ниво в dBFS, под което сигналът се приема за тишина.
- `--silence-duration 2`: минимална продължителност на пауза за обработка.
- `--keep-silence 0.4`: fallback стойност за тишина, ако не са зададени отделни keep параметри.
- `--trim-silence-scope all`: кои паузи да се обработват.
- `--keep-start-silence 0.2`: колко тишина да остане от начална пауза.
- `--keep-middle-silence 0.4`: колко тишина да остане от вътрешни паузи.
- `--keep-end-silence 0.8`: колко тишина да остане от крайна пауза.
- `--silence-channel-mode all`: при multi-channel приема тишина само ако всички канали са под прага.
- `--silence-detection rms`: метод за оценка на тишината.
- `--silence-window 0.02`: прозорец за измерване.
- `--cut-transition none|fade|crossfade`: audio transition на cut местата при concat trim.
- `--cut-fade-duration 0.03`: продължителност на fade/crossfade.
- `--cut-fade-curve tri`: audio fade крива.
- `--video-cut-transition match|none|fade|crossfade`: video transition при video trim. `match` следва audio transition-а.

Scope режими:

- `all`: обработва начало, вътрешни паузи и край. Това е default.
- `edges`: обработва само начална и крайна тишина.
- `start`: обработва само начална тишина.
- `end`: обработва само крайна тишина.
- `middle`: използва повторяем `silenceremove` stop режим за вътрешни паузи. Важно: FFmpeg може да засегне и крайна тишина; за напълно прецизно „само среда“ ще е нужен бъдещ concat-based режим.

За инструментални концертни тракове добър старт е:

```bash
audio_peak_eq.py -i input.wav -o output.wav --trim-silence --silence-threshold -45 --silence-duration 2 --keep-silence 0.4 --overwrite
```

Само начало и край, с различно запазване:

```bash
audio_peak_eq.py -i input.wav -o output.wav --trim-silence --trim-silence-scope edges --keep-start-silence 0.2 --keep-end-silence 0.8 --overwrite
```

Само начална тишина:

```bash
audio_peak_eq.py -i input.wav -o output.wav --trim-silence --trim-silence-scope start --keep-start-silence 0.2 --overwrite
```

Само крайна тишина:

```bash
audio_peak_eq.py -i input.wav -o output.wav --trim-silence --trim-silence-scope end --keep-end-silence 0.8 --overwrite
```

По-консервативен вариант:

```bash
audio_peak_eq.py -i input.wav -o output.wav --trim-silence --silence-threshold -50 --silence-duration 3 --keep-silence 0.7 --overwrite
```

Когато се обработва видео без `--no-video-copy`, `auto` engine избира concat режим. Така видео и аудио се режат по едни и същи времеви диапазони, а при fade/crossfade transition-и визуалните затихвания се прилагат на същите cut места. За audio-only изход от видео използвай `--no-video-copy`.

Fade-out/fade-in на cut местата:

```bash
audio_peak_eq.py -i input.wav -o output.wav --trim-silence --cut-transition fade --cut-fade-duration 0.05 --overwrite
```

Audio crossfade:

```bash
audio_peak_eq.py -i input.wav -o output.wav --trim-silence --cut-transition crossfade --cut-fade-duration 0.08 --overwrite
```

Видео с matching audio/video fade:

```bash
audio_peak_eq.py -i input.mp4 -o output.mp4 --trim-silence --cut-transition fade --video-cut-transition match --cut-fade-duration 0.08 --overwrite
```

Видео с audio/video crossfade:

```bash
audio_peak_eq.py -i input.mp4 -o output.mp4 --trim-silence --cut-transition crossfade --video-cut-transition crossfade --cut-fade-duration 0.08 --overwrite
```

## Примери

Stereo balance + EQ + peak normalization:

```bash
audio_peak_eq.py -i input.wav -o output.wav -B -p vocal_clarity -t -0.5 --overwrite
```

EQ + silence trim + peak normalization:

```bash
audio_peak_eq.py -i input.wav -o output.wav -p car_audio_clarity --trim-silence --silence-duration 2 --keep-silence 0.4 -t -1 --overwrite
```

Multi-channel balance + peak normalization:

```bash
audio_peak_eq.py -i movie.mkv -o movie_fixed.mkv -B --balance-mode all -t -1 --overwrite
```

Само peak normalization:

```bash
audio_peak_eq.py -i input.flac -o output.flac -t -0.5 --overwrite
```
