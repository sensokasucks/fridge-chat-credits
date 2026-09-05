# Credits overlay

Webpage source for **Fridge Chat Credits** (`/overlay/credits.html`).
Stream Core Admin → Credits uses the same overlay files if you run Core instead.

The overlay crawls with `requestAnimationFrame` (not CSS keyframes) so OBS / XSplit CEF keeps moving.

## Look editor

Control desk (standalone) and Admin → Credits (Core) share a tabbed editor:

| Tab | What it edits |
|-----|----------------|
| **Motion** | Presets, motion type, speed, Star Wars tilt, typewriter, Matrix density |
| **Titles** | Title, subtitle, footer, section heading |
| **Type** | Font, sizes, tracking |
| **Color** | Title / name / muted / mod colors, background |
| **Layout** | Columns, width, letterbox / grain / vignette |
| **List** | Sort, grouping, platform dots, mod / VIP highlight |

Live preview applies immediately. **Save look** writes `data/theme.json` (standalone) or Core config. **Restart roll** clears leftover motion and starts again from the top.

Presets always set `name_enter: none` except Classic/Gold/Neon crawls that opt into rise/blur.

## Motions

| Id | What you see |
|----|----------------|
| `crawl` | Names rise from the bottom (classic roll) |
| `crawl-down` | Names fall from the top |
| `starwars` | Yellow crawl on a 3D floor. Loops *before* the vanishing point so it never smears |
| `cards` | One department / page of names at a time (end card). Names are paginated to fit |
| `fade` | Same pages, cross-fade |
| `slides` | Same pages, slide sideways |
| `ticker` | Horizontal name tape |
| `typewriter` | Characters appear with a caret. Unit: line, card, or page |
| `matrix` | Green rain + names decoding in the center |

Opening movie cards + stinger still play on crawl / crawl-down / Star Wars when the movie style file defines them.

## Restart / motion switch

Changing motion type or pressing **Restart roll** hard-resets: animation frame, timers, Matrix canvas, inline transforms, parked reel, page layer. That is what stops a black screen after a glitchy switch.
