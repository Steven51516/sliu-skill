# One driver for several maps

Each driver drives exactly one map.

## Why this is out of scope

A driver that holds several maps mixes their contexts and their claims, and its log no longer reads as one map's story.
One driver per map keeps each session small and replaceable from the files. Seeing every map at once is the desk's job
(and the Research Desk app's), and switching between drivers is cheap in herdr.

## Prior discussion

- 2026-10: a multi-map driver was tried and reverted at the user's request.
